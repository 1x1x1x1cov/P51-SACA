package au.edu.swin.saca;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.window.OnBackInvokedDispatcher;

import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * SACA runs entirely inside this WebView. The page (assets/www/index.html) starts Python with Pyodide and
 * runs the SACA Flask app offline. This activity only serves the app's files, opens phone links (tel:),
 * handles the back button and lets the page use the phone's text-to-speech for "Read aloud".
 */
public class MainActivity extends Activity {

    private static final String TAG = "SACA";
    // Reserved host for app content; requests to it never leave the phone.
    private static final String HOST = "appassets.androidplatform.net";
    private static final String START_URL = "https://" + HOST + "/index.html";

    private WebView web;
    private TextToSpeech tts;
    private volatile boolean ttsReady = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true);  // chrome://inspect on the computer
        }

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0F766E"));
        web = new WebView(this);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(root);

        // Android 15+ draws the app behind the status and navigation bars; keep the page clear of them.
        root.setOnApplyWindowInsetsListener((v, insets) -> {
            int left, top, right, bottom;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                android.graphics.Insets bars = insets.getInsets(
                        WindowInsets.Type.systemBars() | WindowInsets.Type.ime() | WindowInsets.Type.displayCutout());
                left = bars.left; top = bars.top; right = bars.right; bottom = bars.bottom;
            } else {
                left = insets.getSystemWindowInsetLeft(); top = insets.getSystemWindowInsetTop();
                right = insets.getSystemWindowInsetRight(); bottom = insets.getSystemWindowInsetBottom();
            }
            v.setPadding(left, top, right, bottom);
            return insets;
        });

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setTextZoom(100);

        web.setWebViewClient(new AssetClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                Log.d(TAG, m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });

        tts = new TextToSpeech(this, status -> ttsReady = (status == TextToSpeech.SUCCESS));
        tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
            @Override public void onStart(String id) { }
            @Override public void onDone(String id) { if ("saca-last".equals(id)) speechDone(); }
            @Override public void onError(String id) { speechDone(); }
            @Override public void onStop(String id, boolean interrupted) { speechDone(); }
        });
        web.addJavascriptInterface(new SpeechBridge(), "SACAAndroid");

        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::goBack);
        }

        if (savedInstanceState == null || web.restoreState(savedInstanceState) == null) {
            web.loadUrl(START_URL);
        }
    }

    private void goBack() {
        if (web != null && web.canGoBack()) web.goBack();
        else finish();
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {  // Android 12 and older
        goBack();
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (web != null) web.saveState(outState);
    }

    @Override
    protected void onDestroy() {
        if (tts != null) { tts.stop(); tts.shutdown(); }
        if (web != null) { web.destroy(); }
        super.onDestroy();
    }

    private void speechDone() {
        runOnUiThread(() -> {
            if (web != null) web.evaluateJavascript(
                    "window.__sacaSpeechDoneBridge && window.__sacaSpeechDoneBridge()", null);
        });
    }

    /** window.SACAAndroid in the page. Called from the WebView's JavaScript thread. */
    final class SpeechBridge {
        @JavascriptInterface
        public String speak(String text, String lang) {
            if (!ttsReady || text == null) return "error";
            Locale locale = null;
            if ("sw".equals(lang)) {
                Locale[] candidates = { new Locale("sw", "TZ"), new Locale("sw", "KE"), new Locale("sw") };
                for (Locale c : candidates) {
                    if (tts.isLanguageAvailable(c) >= TextToSpeech.LANG_AVAILABLE) { locale = c; break; }
                }
            } else {
                Locale[] candidates = { Locale.UK, Locale.US, Locale.ENGLISH };
                for (Locale c : candidates) {
                    if (tts.isLanguageAvailable(c) >= TextToSpeech.LANG_AVAILABLE) { locale = c; break; }
                }
            }
            if (locale == null) return "nolang";
            tts.setLanguage(locale);
            tts.setSpeechRate("sw".equals(lang) ? 0.9f : 1.0f);
            // Speak sentence by sentence; only the last one reports "done" to the page.
            String[] parts = text.split("(?<=[.!?])\\s+");
            tts.stop();
            for (int i = 0; i < parts.length; i++) {
                String id = (i == parts.length - 1) ? "saca-last" : "saca-" + i;
                int mode = (i == 0) ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD;
                if (tts.speak(parts[i], mode, null, id) != TextToSpeech.SUCCESS) return "error";
            }
            return "ok";
        }

        @JavascriptInterface
        public void stop() {
            if (tts != null) tts.stop();
        }
    }

    /** Serves assets/www for https://appassets.androidplatform.net/ and sends other links to the phone. */
    private final class AssetClient extends WebViewClient {
        private final Map<String, String> types = new HashMap<>();

        AssetClient() {
            types.put("html", "text/html");
            types.put("js", "text/javascript");
            types.put("mjs", "text/javascript");
            types.put("css", "text/css");
            types.put("json", "application/json");
            types.put("wasm", "application/wasm");
            types.put("zip", "application/zip");
            types.put("png", "image/png");
            types.put("svg", "image/svg+xml");
            types.put("map", "application/json");
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            if (!HOST.equals(url.getHost())) return null;
            String path = url.getPath();
            if (path == null || path.equals("/") || path.isEmpty()) path = "/index.html";
            String asset = "www" + path;
            String ext = path.substring(path.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
            String mime = types.containsKey(ext) ? types.get(ext) : "application/octet-stream";
            String encoding = mime.startsWith("text/") || mime.equals("application/json") ? "utf-8" : null;
            try {
                InputStream in = getAssets().open(asset);
                WebResourceResponse r = new WebResourceResponse(mime, encoding, in);
                Map<String, String> headers = new HashMap<>();
                headers.put("Cache-Control", "no-cache");
                headers.put("Access-Control-Allow-Origin", "https://" + HOST);
                r.setResponseHeaders(headers);
                return r;
            } catch (IOException e) {
                Log.w(TAG, "Missing asset " + asset);
                WebResourceResponse r = new WebResourceResponse("text/plain", "utf-8", null);
                r.setStatusCodeAndReasonPhrase(404, "Not Found");
                return r;
            }
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            Uri url = request.getUrl();
            if (HOST.equals(url.getHost())) return false;
            try {
                String scheme = url.getScheme() == null ? "" : url.getScheme();
                Intent intent = "tel".equals(scheme)
                        ? new Intent(Intent.ACTION_DIAL, url)
                        : new Intent(Intent.ACTION_VIEW, url);
                startActivity(intent);
            } catch (ActivityNotFoundException e) {
                Log.w(TAG, "No app for " + url);
            }
            return true;
        }
    }
}
