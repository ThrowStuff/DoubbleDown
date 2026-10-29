// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.InputType;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Spinner;
import android.widget.TextView;

/** Saves local configuration only. Selecting a transport never initiates a connection. */
public final class ConnectionSettingsView extends LinearLayout {
    private static final String[] MODES = {"Bluetooth", "Wi-Fi", "USB"};
    private final SharedPreferences preferences;
    private final Spinner transport;
    private final Spinner usbMode;
    private final EditText computer;
    private final EditText port;
    private final EditText fingerprint;
    private final EditText token;
    private final LinearLayout networkFields;
    private final LinearLayout usbFields;
    private final TextView explanation;
    private final TextView result;

    public ConnectionSettingsView(Context context) {
        super(context);
        setOrientation(VERTICAL);
        preferences = context.getSharedPreferences("connection", Context.MODE_PRIVATE);
        label("Computer connection", 22);
        label("Choose how this phone will connect to your computer. Hearing aids use a separate Bluetooth connection.", 16);
        transport = spinner(MODES);
        explanation = label("", 16);
        networkFields = new LinearLayout(context);
        networkFields.setOrientation(VERTICAL);
        addView(networkFields);
        TextView addressLabel = new TextView(context);
        addressLabel.setText("Computer address");
        networkFields.addView(addressLabel);
        computer = new EditText(context);
        computer.setSingleLine(true);
        computer.setHint("Computer IP address or hostname");
        computer.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        computer.setText(preferences.getString("host", ""));
        networkFields.addView(computer);
        TextView portLabel = new TextView(context);
        portLabel.setText("Port");
        networkFields.addView(portLabel);
        port = new EditText(context);
        port.setSingleLine(true);
        port.setInputType(InputType.TYPE_CLASS_NUMBER);
        port.setText(preferences.getString("port", "49721"));
        networkFields.addView(port);
        TextView pinLabel = new TextView(context);
        pinLabel.setText("Desktop certificate fingerprint (SHA-256)");
        networkFields.addView(pinLabel);
        fingerprint = new EditText(context);
        fingerprint.setSingleLine(true);
        fingerprint.setHint("64 hexadecimal characters from your desktop");
        fingerprint.setText(preferences.getString("fingerprint", ""));
        networkFields.addView(fingerprint);
        TextView tokenLabel = new TextView(context);
        tokenLabel.setText("Desktop session token");
        networkFields.addView(tokenLabel);
        token = new EditText(context);
        token.setSingleLine(true);
        token.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        token.setText(preferences.getString("token", ""));
        networkFields.addView(token);
        usbFields = new LinearLayout(context);
        usbFields.setOrientation(VERTICAL);
        addView(usbFields);
        TextView usbLabel = new TextView(context);
        usbLabel.setText("USB connection method");
        usbFields.addView(usbLabel);
        usbMode = new Spinner(context);
        usbMode.setAdapter(new ArrayAdapter<>(context, android.R.layout.simple_spinner_dropdown_item,
            new String[]{"USB tethering", "USB debugging (ADB)"}));
        usbMode.setSelection(Math.max(0, Math.min(1, preferences.getInt("usbMode", 0))));
        usbFields.addView(usbMode);
        Button save = new Button(context);
        save.setText("Save connection settings");
        addView(save);
        result = label("Settings stay on this phone. Saving does not connect or change the hearing aids.", 16);
        save.setOnClickListener(view -> save());
        transport.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                showMode(position);
                result.setText("Not connected · Save to keep this selection.");
            }
            @Override public void onNothingSelected(AdapterView<?> parent) { }
        });
        int selected = Math.max(0, Math.min(2, preferences.getInt("transport", 0)));
        transport.setSelection(selected);
        showMode(selected);
    }

    private Spinner spinner(String[] choices) {
        Spinner control = new Spinner(getContext());
        control.setAdapter(new ArrayAdapter<>(getContext(), android.R.layout.simple_spinner_dropdown_item, choices));
        addView(control);
        return control;
    }

    private TextView label(String text, int size) {
        TextView label = new TextView(getContext());
        label.setText(text);
        label.setTextSize(size);
        addView(label);
        return label;
    }

    private void showMode(int mode) {
        networkFields.setVisibility(mode != 0 ? VISIBLE : GONE);
        usbFields.setVisibility(mode == 2 ? VISIBLE : GONE);
        if (mode == 0) explanation.setText("Bluetooth relay is planned. We still need to verify the phone’s supported connection roles. Bluetooth computer selection will appear when the relay is available.");
        else if (mode == 1) explanation.setText("Use the same local network as your computer. Enter its address, port, certificate fingerprint and session token from the desktop companion. Verify the fingerprint on your own desktop before connecting.");
        else explanation.setText("For tethering, enter your computer’s USB network address. For ADB, configure adb reverse tcp:49721 tcp:49721 on your computer; the phone connects to localhost. The app does not enable tethering or debugging for you. Both methods verify the desktop certificate.");
    }

    private void save() {
        int mode = transport.getSelectedItemPosition();
        String host = computer.getText().toString().trim();
        String portText = port.getText().toString().trim();
        if (mode != 0) {
            if (!(mode==2 && usbMode.getSelectedItemPosition()==1) && (host.isEmpty() || host.matches(".*\\s+.*") || host.contains("://") || host.contains("/"))) {
                computer.setError("Enter an IP address or hostname, without a URL or spaces");
                computer.requestFocus();
                return;
            }
            if (!fingerprint.getText().toString().replace(":", "").trim().matches("(?i)[0-9a-f]{64}")) {
                fingerprint.setError("Copy the desktop SHA-256 certificate fingerprint");
                fingerprint.requestFocus();
                return;
            }
            if (!token.getText().toString().trim().matches("[0-9a-f]{64}")) {
                token.setError("Copy the 64-character desktop session token");
                token.requestFocus();
                return;
            }
            try {
                int number = Integer.parseInt(portText);
                if (number < 1 || number > 65535) throw new NumberFormatException();
            } catch (NumberFormatException error) {
                port.setError("Enter a port from 1 to 65535");
                port.requestFocus();
                return;
            }
        }
        preferences.edit().putInt("transport", mode)
            .putString("host", host).putString("port", portText)
            .putString("fingerprint", fingerprint.getText().toString().trim())
            .putString("token", token.getText().toString().trim())
            .putInt("usbMode", usbMode.getSelectedItemPosition()).apply();
        result.setText(MODES[mode] + " settings saved · Not connected.");
    }
}
