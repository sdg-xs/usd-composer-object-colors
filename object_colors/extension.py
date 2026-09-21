import omni.ext
import omni.kit.commands
import omni.kit.menu.utils

from .controller import ChangeObjectColors, Controller
from .window import ObjectColorsWindow


class ObjectColorsExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        omni.kit.commands.register(ChangeObjectColors)
        self.controller = Controller()
        self.panel = ObjectColorsWindow(self.controller)
        self.menu = [omni.kit.menu.utils.MenuItemDescription(name='Object Colors', onclick_fn=self.panel.show)]
        omni.kit.menu.utils.add_menu_items(self.menu, 'Window')

    def on_shutdown(self):
        omni.kit.menu.utils.remove_menu_items(self.menu, 'Window')
        self.panel.close()
        self.controller.close()
        omni.kit.commands.unregister(ChangeObjectColors)
