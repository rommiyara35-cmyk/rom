import Toybox.Graphics;
import Toybox.WatchUi;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.Timer;

class SoloLevelingView extends WatchUi.View {
    // 416x416 AMOLED Venu 4 Constants
    private var _screenWidth as Number = 416;
    private var _screenHeight as Number = 416;
    
    // Hunter Data
    public var rank as String = "E-Rank";
    public var level as Number = 1;
    public var calories as Number = 0;
    public var caloriesTarget as Number = 2180;
    public var protein as Float = 0.0;
    public var proteinTarget as Number = 160;
    public var carbs as Float = 0.0;
    public var carbsTarget as Number = 220;
    public var fats as Float = 0.0;
    public var fatsTarget as Number = 65;
    public var water as Number = 0;
    public var waterTarget as Number = 3000;

    // Local Server URL (Configurable in Connect IQ App Settings)
    public var serverUrl as String = "http://192.168.1.50:8080/api/garmin/status";
    private var _timer as Timer.Timer?;

    function initialize() {
        View.initialize();
        _timer = new Timer.Timer();
    }

    function onLayout(dc as Dc) as Void {
        _screenWidth = dc.getWidth();
        _screenHeight = dc.getHeight();
    }

    function onShow() as Void {
        fetchStatus();
        if (_timer != null) {
            _timer.start(method(:fetchStatus), 30000, true); // Refresh every 30s
        }
    }

    function onHide() as Void {
        if (_timer != null) {
            _timer.stop();
        }
    }

    function fetchStatus() as Void {
        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        Communications.makeWebRequest(
            serverUrl,
            null,
            options,
            method(:onReceiveStatus)
        );
    }

    function onReceiveStatus(responseCode as Number, data as Dictionary or Null) as Void {
        if (responseCode == 200 && data != null) {
            if (data.hasKey("rank")) { rank = data["rank"] as String; }
            if (data.hasKey("lvl")) { level = data["lvl"] as Number; }
            if (data.hasKey("cal")) { calories = data["cal"] as Number; }
            if (data.hasKey("cal_tgt")) { caloriesTarget = data["cal_tgt"] as Number; }
            if (data.hasKey("p")) { protein = (data["p"] as Numeric).toFloat(); }
            if (data.hasKey("p_tgt")) { proteinTarget = data["p_tgt"] as Number; }
            if (data.hasKey("c")) { carbs = (data["c"] as Numeric).toFloat(); }
            if (data.hasKey("c_tgt")) { carbsTarget = data["c_tgt"] as Number; }
            if (data.hasKey("f")) { fats = (data["f"] as Numeric).toFloat(); }
            if (data.hasKey("f_tgt")) { fatsTarget = data["f_tgt"] as Number; }
            if (data.hasKey("w")) { water = data["w"] as Number; }
            if (data.hasKey("w_tgt")) { waterTarget = data["w_tgt"] as Number; }
            WatchUi.requestUpdate();
        }
    }

    function onUpdate(dc as Dc) as Void {
        // True Black AMOLED Background
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();

        var cx = _screenWidth / 2;
        var cy = _screenHeight / 2;
        var radius = cx - 18;

        // 1. Draw Outer Background Track
        dc.setColor(0x1a2333, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(12);
        dc.drawCircle(cx, cy, radius);

        // 2. Draw Calorie Progress Arc (Cyan Glow)
        var pct = calories.toFloat() / (caloriesTarget > 0 ? caloriesTarget : 1);
        if (pct > 1.0) { pct = 1.0; }
        if (pct > 0.0) {
            var sweep = (pct * 360.0).toNumber();
            dc.setColor(0x00f0ff, Graphics.COLOR_TRANSPARENT);
            dc.setPenWidth(12);
            // In Connect IQ, angles: 90 is top (12 o'clock), 0 is 3 o'clock
            dc.drawArc(cx, cy, radius, Graphics.ARC_COUNTER_CLOCKWISE, 90, 90 - sweep);
        }

        // 3. Draw Rank & Level Badge
        dc.setColor(0x00f0ff, Graphics.COLOR_TRANSPARENT);
        var badgeText = rank.toUpper() + " [LV. " + level.toString() + "]";
        dc.drawText(cx, cy - 85, Graphics.FONT_TINY, badgeText, Graphics.TEXT_JUSTIFY_CENTER);

        // 4. Draw Center Calorie Number
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, cy - 45, Graphics.FONT_NUMBER_HOT, calories.toString(), Graphics.TEXT_JUSTIFY_CENTER);

        // Calorie target label
        dc.setColor(0x94a3b8, Graphics.COLOR_TRANSPARENT);
        var targetStr = "/ " + caloriesTarget.toString() + " KCAL";
        dc.drawText(cx, cy + 18, Graphics.FONT_XTINY, targetStr, Graphics.TEXT_JUSTIFY_CENTER);

        // 5. Draw Macro Mini Stats (P / C / F)
        var pStr = "P:" + protein.toNumber().toString() + "g";
        var cStr = "C:" + carbs.toNumber().toString() + "g";
        var fStr = "F:" + fats.toNumber().toString() + "g";
        
        dc.setColor(0xef4444, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx - 65, cy + 48, Graphics.FONT_XTINY, pStr, Graphics.TEXT_JUSTIFY_CENTER);
        
        dc.setColor(0x3b82f6, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, cy + 48, Graphics.FONT_XTINY, cStr, Graphics.TEXT_JUSTIFY_CENTER);
        
        dc.setColor(0xf59e0b, Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx + 65, cy + 48, Graphics.FONT_XTINY, fStr, Graphics.TEXT_JUSTIFY_CENTER);

        // 6. Draw Water Status Pill at bottom
        dc.setColor(0x0a1c36, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(cx - 70, cy + 80, 140, 26, 13);
        dc.setColor(0x00f0ff, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(1);
        dc.drawRoundedRectangle(cx - 70, cy + 80, 140, 26, 13);

        var waterStr = "HP: " + water.toString() + "/" + waterTarget.toString() + " ml";
        dc.drawText(cx, cy + 83, Graphics.FONT_XTINY, waterStr, Graphics.TEXT_JUSTIFY_CENTER);
    }
}
