import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class SoloLevelingApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
    }

    function onStop(state as Dictionary?) as Void {
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        var view = new SoloLevelingView();
        var delegate = new SoloLevelingDelegate(view);
        return [view, delegate];
    }
}
