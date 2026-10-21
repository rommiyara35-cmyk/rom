import Toybox.Background;
import Toybox.System;
import Toybox.Communications;
import Toybox.ActivityMonitor;
import Toybox.SensorHistory;
import Toybox.Application;
import Toybox.Lang;

// Background service: pushes watch biometrics to the server every time the
// system fires our temporal event (registered for 15 min in SoloLevelingApp).
// Runs without the widget open. Battery-friendly: one short HTTPS POST per
// cycle, skipped entirely when the phone is not connected.
(:background)
class SoloLevelingBackground extends System.ServiceDelegate {

    function initialize() {
        ServiceDelegate.initialize();
    }

    function onTemporalEvent() as Void {
        pushMetrics();
    }

    // Single source of truth for the server URL (see SoloLevelingApp).
    private function serverBase() as String {
        try {
            var app = Application.getApp() as SoloLevelingApp;
            if (app != null && app.serverBaseUrl != null) {
                return app.serverBaseUrl;
            }
        } catch (e) {
        }
        return "https://rom-z019.onrender.com";
    }

    private function pushMetrics() as Void {
        // No phone link -> nothing to send through; next cycle retries.
        var settings = System.getDeviceSettings();
        if (settings == null || !settings.phoneConnected) {
            Background.exit(null);
            return;
        }

        var params = {};
        try {
            var info = ActivityMonitor.getInfo();
            if (info != null) {
                if (info.steps != null) { params["steps"] = info.steps; }
                if (info.calories != null) { params["active_calories"] = info.calories; }
                if (info.distance != null) { params["distance_m"] = info.distance; }
            }
            var hr = latestHeartRate();
            if (hr != null) { params["heart_rate"] = hr; }
        } catch (e) {
            // Sensor read failed; push whatever we managed to collect.
        }
        // "connect_iq" is a recognized real sync_source on the server
        // (counts for the Attent biometric filter).
        params["source"] = "connect_iq";

        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_POST,
            :headers => { "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON },
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        var url = serverBase() + "/api/garmin/webhook";
        Communications.makeWebRequest(url, params, options, method(:onPushDone));
    }

    // Newest heart-rate sample from the on-device history (may be null if
    // the optical sensor has no recent reading).
    private function latestHeartRate() as Number or Null {
        try {
            var iter = SensorHistory.getHeartRateHistory({
                :period => 1,
                :order => SensorHistory.ORDER_NEWEST_FIRST
            });
            if (iter != null) {
                var sample = iter.next();
                if (sample != null && sample.heartRate != null
                    && sample.heartRate != SensorHistory.INVALID_HR_SAMPLE) {
                    return sample.heartRate;
                }
            }
        } catch (e) {
        }
        return null;
    }

    private function onPushDone(responseCode as Number, data as Dictionary or Null) as Void {
        // Success or failure, we're done: a failed push is simply retried
        // on the next 15-minute cycle. Must call exit() to release the
        // background slot.
        Background.exit(null);
    }
}
