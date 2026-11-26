import QtQuick
import QtTest
import "../../ui/jarvis_shell"
TestCase {
    name: "NativeWidgetSurface"
    when: windowShown
    width: 500; height: 400
    ArcReactorCore { id: reactor; width: 100; height: 100 }
    function test_content_controls_and_reactions() {
        reactor.voiceState = "complete";
        compare(reactor.statusText, "COMPLETE");
        reactor.voiceState = "alert";
        compare(reactor.accent, "#ff5577");
        wait(30);
    }
}
