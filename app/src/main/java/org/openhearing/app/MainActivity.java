// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothStatusCodes;
import android.content.pm.PackageManager;
import android.media.AudioDeviceCallback;
import android.media.AudioDeviceInfo;
import android.media.AudioManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Initial read-only device inventory. Never connects, scans, pairs or records. */
public final class MainActivity extends Activity {
    private TextView details;
    private AudioManager audio;
    private RelayControlsView relay;
    private boolean callbackRegistered;
    private final AudioDeviceCallback callback = new AudioDeviceCallback() {
        @Override public void onAudioDevicesAdded(AudioDeviceInfo[] devices) { refresh(); }
        @Override public void onAudioDevicesRemoved(AudioDeviceInfo[] devices) { refresh(); }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        audio = getSystemService(AudioManager.class);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = (int) (20 * getResources().getDisplayMetrics().density);
        content.setPadding(padding, padding, padding, padding);
        TextView title = new TextView(this);
        title.setText("PassThrough");
        title.setTextSize(28);
        content.addView(title);
        TextView status = new TextView(this);
        status.setText("Development preview · Device inventory\nYour current hearing-aid connection stays unchanged.");
        content.addView(status);
        content.addView(new ConnectionSettingsView(this));
        relay = new RelayControlsView(this);
        content.addView(relay);
        Button refresh = new Button(this);
        refresh.setText("Refresh audio devices");
        refresh.setOnClickListener(view -> refresh());
        content.addView(refresh);
        Button bluetooth = new Button(this);
        bluetooth.setText("Check Bluetooth capability");
        bluetooth.setOnClickListener(view -> {
            if (android.os.Build.VERSION.SDK_INT>=31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.BLUETOOTH_CONNECT}, 1);
            } else refresh();
        });
        content.addView(bluetooth);
        details = new TextView(this);
        details.setTextSize(16);
        details.setTextIsSelectable(true);
        content.addView(details);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(content);
        setContentView(scroll);
        refresh();
    }

    @Override protected void onStart() {
        super.onStart();
        if (audio != null) {
            audio.registerAudioDeviceCallback(callback, new Handler(Looper.getMainLooper()));
            callbackRegistered = true;
        }
        refresh();
    }

    @Override protected void onStop() {
        if (callbackRegistered) {
            audio.unregisterAudioDeviceCallback(callback);
            callbackRegistered = false;
        }
        super.onStop();
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        refresh();
    }

    private void refresh() {
        if (details == null) return;
        if (relay != null) relay.updateDevices();
        StringBuilder text = new StringBuilder();
        BluetoothManager manager = getSystemService(BluetoothManager.class);
        BluetoothAdapter adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null) text.append("Bluetooth unavailable on this device.\n");
        else if (android.os.Build.VERSION.SDK_INT>=31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            text.append("Bluetooth capability: permission not granted.\n");
        } else {
            try {
                text.append("Bluetooth: ").append(adapter.isEnabled() ? "on" : "off").append('\n');
                if (android.os.Build.VERSION.SDK_INT >= 33) {
                    int capability = adapter.isLeAudioSupported();
                    text.append("LE Audio capability: ")
                        .append(capability == BluetoothStatusCodes.FEATURE_SUPPORTED ? "supported" :
                            capability == BluetoothStatusCodes.FEATURE_NOT_SUPPORTED ? "not supported" :
                            "unavailable (status " + capability + ")")
                        .append('\n');
                }
            } catch (SecurityException error) {
                text.append("Bluetooth permission was revoked.\n");
            }
        }
        if (audio == null) text.append("Audio service unavailable.\n");
        else {
            text.append("\nAvailable audio devices\n");
            for (AudioDeviceInfo device : audio.getDevices(AudioManager.GET_DEVICES_INPUTS | AudioManager.GET_DEVICES_OUTPUTS)) {
                text.append(device.isSource() ? "Input: " : "Output: ")
                    .append(device.getProductName()).append(" · ")
                    .append(typeName(device.getType())).append('\n');
            }
        }
        text.append("\nOn the Pixel 7 test setup, Android verified the selected hearing-aid microphone route and a known speaker-played tone matched the uplink. Other devices and speech quality still need testing.\n")
            .append("\nProgram controls are not implemented yet. Computer audio uses the separate Wi-Fi/USB desktop link; the live relay test used ADB forwarding. Direct LAN and physical USB remain untested.");
        details.setText(text.toString());
    }

    private static String typeName(int type) {
        if (android.os.Build.VERSION.SDK_INT>=37 && type==33) return "LE Audio hearing aid";
        switch (type) {
            case AudioDeviceInfo.TYPE_BLE_HEADSET: return "LE Audio headset";
            case AudioDeviceInfo.TYPE_HEARING_AID: return "ASHA hearing aid";
            case AudioDeviceInfo.TYPE_BLUETOOTH_A2DP: return "Bluetooth media";
            case AudioDeviceInfo.TYPE_BLUETOOTH_SCO: return "Bluetooth call audio";
            case AudioDeviceInfo.TYPE_BUILTIN_MIC: return "phone microphone";
            case AudioDeviceInfo.TYPE_BUILTIN_SPEAKER: return "phone speaker";
            default: return "device type " + type;
        }
    }
}
