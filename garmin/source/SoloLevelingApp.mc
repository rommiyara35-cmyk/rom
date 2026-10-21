import Toybox.Application;
import Toybox.Background;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.WatchUi;

class SoloLevelingApp extends Application.AppBase {

    // Single source of truth for the server URL. The widget, its delegate
    // and the background service all read this. Update here if the Render
    // URL ever changes, then recompile.
    public var serverBaseUrl as String = "https://rom-z019.onrender.com";

    function initialize() {
        AppBase.initialize();
    }

    function onStart(state as Dictionary?) as Void {
        // Battery-friendly background push: the system wakes our background
        // service every 15 minutes to send steps/HR to the server, even when
        // the widget is not open. (Widget must be opened once after install
        // for the registration to take effect.)
        try {
            Background.registerForTemporalEvent(new Time.Duration(15 * 60));
        } catch (e) {
            // Background unavailable on this device; foreground sync still works.
        }
    }

    function onStop(state as Dictionary?) as Void {
    }

    function getServiceDelegate() as [System.ServiceDelegate] {
        return [new SoloLevelingBackground()];
    }

    function getInitialView() as [Views] or [Views, InputDelegates] {
        var view = new SoloLevelingView();
        var delegate = new SoloLevelingDelegate(view);
        return [view, delegate];
    }
}
