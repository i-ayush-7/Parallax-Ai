const { app, BrowserWindow, desktopCapturer, session } = require('electron');
const path = require('path');

// THE FIX: Bypass GPU driver glitches that cause invisible windows
app.disableHardwareAcceleration();

function createWindow() {
    const win = new BrowserWindow({
        width: 360,
        height: 750,
        alwaysOnTop: true,
        transparent: true,
        frame: false,
        hasShadow: false,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    session.defaultSession.setDisplayMediaRequestHandler((request, callback) => {
        desktopCapturer.getSources({ types: ['screen'] }).then((sources) => {
            callback({ video: sources[0] });
        }).catch(err => {
            console.error("Screen capture routing failed:", err);
        });
    });

    const { width: screenWidth } = require('electron').screen.getPrimaryDisplay().workAreaSize;
    win.setPosition(screenWidth - 420, 20);

    win.loadFile('index.html');
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});