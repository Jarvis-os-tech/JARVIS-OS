import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    FloatingWindow {
        title: "Connect Gemini to JARVIS"
        implicitWidth: 530
        implicitHeight: 250
        color: "#101923"
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 10
            Label { text: "Connect Gemini"; color: "white"; font.pixelSize: 24 }
            Label { text: "Copy a key from Google AI Studio in this VM, then paste it here."; color: "#cedce5"; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            TextField {
                id: key
                Layout.fillWidth: true
                focus: true
                placeholderText: "Gemini API key"
                echoMode: TextInput.Password
                selectByMouse: true
                onAccepted: if (save.enabled) save.clicked()
            }
            RowLayout {
                Button { text: "Open AI Studio"; onClicked: browser.running = true }
                Button { text: "Paste"; onClicked: { key.forceActiveFocus(); key.selectAll(); key.paste() } }
                Button {
                    id: save
                    text: "Continue"
                    onClicked: {
                        let value = key.text.trim().replace(/^(?:export\s+)?(?:GEMINI_API_KEY|GOOGLE_API_KEY)\s*=\s*/, "").trim()
                        value = value.replace(/^(['"])(.*)\1$/, "$2")
                        if (!/^[A-Za-z0-9_.-]+$/.test(value)) {
                            feedback.text = "Use the copy icon beside the key, then click Paste."
                            return
                        }
                        output.setText("GEMINI_API_KEY=" + value + "\n")
                    }
                }
            }
            Label { id: feedback; color: "#cedce5"; text: key.length ? key.length + " characters entered" : "Waiting for a key" }
        }
    }
    FileView {
        id: output
        path: Quickshell.env("JARVIS_SETUP_TEMP")
        atomicWrites: false
        onSaved: Qt.quit()
        onSaveFailed: feedback.text = "Could not save the key. Try again."
    }
    Process {
        id: browser
        command: ["env", "LD_LIBRARY_PATH=/opt/voice-os/browser-libs", "/opt/voice-os/chromium/chromium", "--ozone-platform=wayland", "--new-window", "https://aistudio.google.com/apikey"]
    }
}
