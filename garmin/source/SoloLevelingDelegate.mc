import Toybox.WatchUi;
import Toybox.Communications;
import Toybox.Lang;

class SoloLevelingDelegate extends WatchUi.BehaviorDelegate {
    private var _view as SoloLevelingView;

    function initialize(view as SoloLevelingView) {
        BehaviorDelegate.initialize();
        _view = view;
    }

    // Tap screen on Venu 4 to log +250ml water immediately
    function onTap(evt as ClickEvent) as Boolean {
        var xy = evt.getCoordinates();
        // If tapped in bottom half
        if (xy[1] > 280) {
            logWater();
            return true;
        }
        // If tapped in center, force refresh
        _view.fetchStatus();
        return true;
    }

    function logWater() as Void {
        var url = "http://192.168.1.50:8080/api/garmin/quick-water";
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => { "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON },
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        var params = { "amount_ml" => 250 };
        Communications.makeWebRequest(url, params, options, method(:onWaterLogged));
    }

    function onWaterLogged(responseCode as Number, data as Dictionary or Null) as Void {
        if (responseCode == 200) {
            _view.fetchStatus();
        }
    }
}
