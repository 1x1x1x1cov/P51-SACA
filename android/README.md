# SACA for Android

Part of the SACA repository. See also `docs/SACA_Handover_Documentation.docx`, Part 4, section 6.

The SACA app as an Android app. It runs fully offline on the phone: the SACA Python app (the same code as the
P51-SACA repository) runs inside the app with Pyodide, Python compiled to WebAssembly. There is no server and
no internet permission.

## Install on a phone (Samsung S21 or any Android 8.0+)

1. Open this folder (`android/` in the SACA repository) in Android Studio with **File > Open**, and wait for Gradle sync.
2. On the phone, turn on USB debugging: **Settings > About phone > Software information**, tap **Build number**
   seven times, then **Settings > Developer options > USB debugging** on.
3. Plug the phone in, allow the computer on the phone, choose the phone in the device list and press **Run**.

To get an APK file instead: **Build > Generate App Bundles or APKs > Generate APKs**. The file is
`app/build/outputs/apk/debug/app-debug.apk`. Copy it to the phone and open it (allow "Install unknown apps").

The first start takes about 5 to 15 seconds while Python loads. Signing in takes a second or two because
PINs and passwords are hashed with 600,000 PBKDF2 rounds.

## What works and what does not

- Works offline: sign-in (guest, family PIN, health worker), assessment, Body Map, result cards,
  history, contacts (tapping a number opens the phone dialler), Swahili screens, dark mode.
- Data stays on the phone, in the app's storage. Uninstalling the app deletes it.
- Read aloud uses the phone's own text-to-speech. English works on every phone. For Swahili, the phone
  needs a Swahili voice (Settings > General management > Text-to-speech); if there is none, the app says so.
- Not included: voice input (speech-to-text) and the LLM symptom extractor. Both need the internet and an
  API key, so the "Speak instead" button is hidden.

## How it is built

- `app/src/main/assets/www/` is the whole app: `index.html` and `boot.js` start Pyodide (`pyodide/`), unpack
  `app.zip` (the SACA Python app plus pure-Python Flask) and pass every link and form to Flask's test
  client. `/data` is kept in the WebView's IndexedDB.
- The phone has no scikit-learn, so the trained model is loaded from `dataset_v2/saca_v2_model.json`
  (`classifier/portable_model.py`). `tests/test_portable_model.py` in the repository checks it gives the
  same result as scikit-learn on all 1,655 held-out symptom sets.
- `MainActivity.java` serves those files from `https://appassets.androidplatform.net/`, opens `tel:` links,
  handles Back and gives the page the phone's text-to-speech.

After changing the SACA app, rebuild `app.zip` from the repository root and run the app again:

    python mobile/build_android_assets.py android

## If something goes wrong

- **Gradle sync fails:** this project uses Gradle 9.5.0, Android Gradle Plugin 9.3.3 and a Java 25 toolchain.
  Use a current Android Studio and **File > Sync Project with Gradle Files** once.
- **White or green screen with an error box:** the message shows what failed. For more detail, open
  `chrome://inspect` in Chrome on the computer with the phone plugged in, and inspect the SACA page.
- **Logcat:** filter by the tag `SACA` to see the page's console messages.
