pragma Singleton
import QtQuick

QtObject {
    readonly property string locale: shellBridge ? shellBridge.locale : "en"
    function t(key) {
        // Reading the notifying property makes every caller a live binding.
        var current = locale
        return shellBridge ? shellBridge.translate(key) : key
    }
}
