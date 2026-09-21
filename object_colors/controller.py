"""Kit lifecycle and undo orchestration around the stage-local coloring engine."""

import asyncio
from time import perf_counter
import weakref

import carb
import omni.kit.app
import omni.kit.commands
import omni.usd

from .discovery import HOOPS, Scan, scan_steps
from .overrides import ColorOverrides
from .presets import dumps, load_scene, loads, save_scene
from .scheme import Scheme, group_objects


class ChangeObjectColors(omni.kit.commands.Command):
    def __init__(self, controller, before: str, after: str):
        self.controller = weakref.ref(controller)
        self.generation = controller.generation
        self.before = before
        self.after = after

    def _restore(self, text):
        controller = self.controller()
        if controller and controller.generation == self.generation and controller.alive:
            controller.restore(text)

    def do(self):
        self._restore(self.after)

    def undo(self):
        self._restore(self.before)


class Controller:
    def __init__(self):
        self.stage = None
        self.overrides = None
        self.scheme = Scheme()
        self.scan = Scan()
        self.groups = []
        self.status = 'Open a USD stage to discover object properties.'
        self.issues = []
        self.busy = False
        self.generation = 0
        self.alive = True
        self.listeners = []
        self.task = None
        self.context = omni.usd.get_context()
        self.subscription = self.context.get_stage_event_stream().create_subscription_to_pop(
            self._stage_event, name='object.color.stage')
        self.attach(self.context.get_stage())

    def notify(self, rebuild=True):
        for listener in tuple(self.listeners):
            listener(rebuild)

    def _stage_event(self, event):
        if event.type == int(omni.usd.StageEventType.OPENED):
            self.attach(self.context.get_stage())
        elif event.type == int(omni.usd.StageEventType.CLOSING):
            self.attach(None)

    def attach(self, stage):
        self.generation += 1
        if self.task:
            self.task.cancel()
        if self.overrides:
            self.overrides.close()
        self.stage = stage
        self.overrides = ColorOverrides(stage) if stage else None
        self.scan = Scan()
        self.groups = []
        self.busy = False
        self.issues = []
        try:
            self.scheme = load_scene(stage) if stage else Scheme()
        except ValueError as exc:
            self.scheme = Scheme()
            self.issues = [f'Saved scene colors could not be loaded: {exc}']
        if stage:
            self._schedule(True, persist=False)
        else:
            self.status = 'Open a USD stage to discover object properties.'
            self.notify()

    def edit(self, *, mode=None, property_key=None, enabled=None, color=None):
        _, scheme = loads(dumps('Current', self.scheme))
        if mode is not None:
            scheme.mode = mode
        if property_key is not None:
            scheme.property_key = property_key
        if enabled is not None:
            scheme.enabled = enabled
        if color is not None:
            scheme.set_color(*color)
        self.change(scheme)

    def change(self, scheme):
        omni.kit.commands.execute('ChangeObjectColors', controller=self,
                                  before=dumps('Current', self.scheme), after=dumps('Current', scheme))

    def restore(self, text):
        _, self.scheme = loads(text)
        self._schedule(False)

    def refresh(self):
        self._schedule(True)

    def _schedule(self, rescan, persist=True):
        if not self.stage:
            return
        if self.task:
            self.task.cancel()
        self.task = asyncio.ensure_future(self._update(rescan, self.generation, persist))

    async def _drive(self, steps, label):
        try:
            while True:
                try:
                    progress = next(steps)
                except StopIteration as done:
                    return done.value
                self.status = f'{label} {progress:.0%}' if isinstance(progress, float) else f'{label} {progress:,} prims'
                self.notify(False)
                await omni.kit.app.get_app().next_update_async()
        finally:
            steps.close()

    async def _update(self, rescan, generation, persist):
        overrides = self.overrides
        stage = self.stage
        if overrides is None or stage is None:
            return
        start = perf_counter()
        self.busy = True
        self.notify()
        try:
            if rescan:
                self.scan = await self._drive(scan_steps(self.stage), 'Scanning')
                if not self.scheme.property_key and self.scan.properties:
                    self.scheme.property_key = (HOOPS + 'TYPE' if HOOPS + 'TYPE' in self.scan.properties else self.scan.properties[0])
            self.groups = group_objects(self.scan.objects, self.scheme)
            self.issues = list(self.scan.issues)
            reason = self.scan.unavailable_reason(self.scheme.mode)
            if self.scheme.mode == 'Property' and self.scheme.property_key not in self.scan.properties:
                reason = 'The selected property is absent. Choose a property or load a compatible scene.'
            if reason:
                self.issues.append(reason)
            if self.scheme.enabled and not reason:
                colors = {p: g.color for g in self.groups for p in g.objects}
                assignments = {target: colors[obj.path] for obj in self.scan.objects
                               for target in obj.targets if colors[obj.path] is not None}
                overrides.enabled = True
                report = await self._drive(overrides.apply_steps(assignments), 'Applying colors')
                self.issues.extend(report.issues)
                detail = f'{report.colored:,} render targets colored'
            else:
                overrides.set_enabled(False)
                detail = 'Colors off' if not self.scheme.enabled else 'No colors applied'
            if persist and not save_scene(self.stage, self.scheme):
                self.issues.append('Scene is read-only. Export a preset to retain these choices.')
            self.status = f'{len(self.scan.objects):,} objects | {detail} | {perf_counter() - start:.2f}s'
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.status = f'Could not update colors: {exc}'
            self.issues.append(str(exc))
            carb.log_error(self.status)
        finally:
            if generation == self.generation and asyncio.current_task() is self.task:
                self.busy = False
                self.notify()

    def close(self):
        self.alive = False
        self.generation += 1
        self.subscription = None
        if self.task:
            self.task.cancel()
            self.task = None
        if self.overrides:
            self.overrides.close()
            self.overrides = None
        self.listeners.clear()
        self.stage = None
