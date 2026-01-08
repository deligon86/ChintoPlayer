import  os
from bootstrap import bootstrap
from kivymd_interface.app import ReloMusicPlayerApp
from kivymd_interface.views.mainview import MainView


# set env
os.environ['WORKING_DIR'] = os.getcwd()

# presentation with kivymd
context = bootstrap()
main_window = MainView   # due to material design specs the window will be inited in build
app = ReloMusicPlayerApp(context=context, main_window=main_window)
context.get("scheduler").start_loop()
app.run()
# on exit
#context['scheduler'].stop()
