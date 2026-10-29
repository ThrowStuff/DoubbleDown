// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.*;
import android.os.*;
import android.widget.*;
import java.util.ArrayList;
import java.util.List;

public final class RelayControlsView extends LinearLayout {
    private final Activity activity;
    private final Spinner output;
    private final Spinner input;
    private final CheckBox microphone;
    private final TextView state;
    private final List<Integer> outputIds = new ArrayList<>();
    private final List<Integer> inputIds = new ArrayList<>();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable tick = new Runnable() {
        private String last="";
        @Override public void run() {
            if (!last.equals(RelayService.status)) { last=RelayService.status; state.setText(last); }
            handler.postDelayed(this,1000);
        }
    };

    public RelayControlsView(Activity context) {
        super(context);
        activity=context;
        setOrientation(VERTICAL);
        label("Audio relay",22);
        label("Select hearing-device routes. The phone microphone and speaker are excluded. Start only after arranging a handover from your current computer connection.",16);
        label("Playback output",16);
        output=new Spinner(context); addView(output);
        microphone=new CheckBox(context);
        microphone.setText("Send the selected hearing-device microphone to the computer");
        addView(microphone);
        label("Microphone input (LE Audio required)",16);
        input=new Spinner(context); addView(input);
        Button start=new Button(context); start.setText("Start relay"); addView(start);
        start.setOnClickListener(view -> start());
        Button stop=new Button(context); stop.setText("Stop relay"); addView(stop);
        stop.setOnClickListener(view -> context.startService(new Intent(context,RelayService.class).setAction("stop")));
        state=label(RelayService.status,16);
        Button notifications=new Button(context);
        notifications.setText("Enable relay notification"); addView(notifications);
        notifications.setOnClickListener(view -> {
            if (Build.VERSION.SDK_INT>=33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) {
                activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},3);
            } else state.setText("Notification permission is available. Start/stop controls also remain in this app.");
        });
        updateDevices();
    }
    private TextView label(String text,int size) {
        TextView view=new TextView(getContext()); view.setText(text); view.setTextSize(size); addView(view); return view;
    }
    @Override protected void onAttachedToWindow() { super.onAttachedToWindow(); handler.post(tick); }
    @Override protected void onDetachedFromWindow() { handler.removeCallbacks(tick); super.onDetachedFromWindow(); }

    public void updateDevices() {
        int oldOutput=selectedId(output,outputIds), oldInput=selectedId(input,inputIds);
        outputIds.clear(); inputIds.clear();
        outputIds.add(-1); inputIds.add(-1);
        List<String> outputs=new ArrayList<>(), inputs=new ArrayList<>();
        outputs.add("Choose a hearing-device output"); inputs.add("Choose an LE Audio microphone");
        AudioManager manager=getContext().getSystemService(AudioManager.class);
        if (manager!=null) for (AudioDeviceInfo device:manager.getDevices(AudioManager.GET_DEVICES_INPUTS | AudioManager.GET_DEVICES_OUTPUTS)) {
            int type=device.getType();
            if (!HearingRoutes.isOutput(type)) continue;
            String name=device.getProductName()+" · "+(type==AudioDeviceInfo.TYPE_HEARING_AID ? "ASHA" : "LE Audio");
            if (device.isSink()) { outputIds.add(device.getId()); outputs.add(name); }
            if (device.isSource() && HearingRoutes.isLeHearingDevice(type)) { inputIds.add(device.getId()); inputs.add(name); }
        }
        output.setAdapter(new ArrayAdapter<>(getContext(),android.R.layout.simple_spinner_dropdown_item,outputs));
        input.setAdapter(new ArrayAdapter<>(getContext(),android.R.layout.simple_spinner_dropdown_item,inputs));
        output.setSelection(Math.max(0,outputIds.indexOf(oldOutput)));
        input.setSelection(Math.max(0,inputIds.indexOf(oldInput)));
    }
    private int selectedId(Spinner spinner,List<Integer> ids) {
        int index=spinner.getSelectedItemPosition();
        return index>=0 && index<ids.size() ? ids.get(index) : -1;
    }
    private void start() {
        int out=selectedId(output,outputIds), in=selectedId(input,inputIds);
        if (out<0) { state.setText("Choose an available hearing-device output first."); return; }
        if (microphone.isChecked() && Build.VERSION.SDK_INT<31) { state.setText("Hearing-device microphone routing requires Android 12 or newer and a compatible audio route."); return; }
        if (microphone.isChecked() && in<0) { state.setText("No selected LE Audio microphone. ASHA playback does not provide microphone input."); return; }
        List<String> permissions=new ArrayList<>();
        if (Build.VERSION.SDK_INT>=31 && activity.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED) permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
        if (microphone.isChecked() && activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) permissions.add(Manifest.permission.RECORD_AUDIO);
        if (!permissions.isEmpty()) {
            activity.requestPermissions(permissions.toArray(new String[0]),2);
            state.setText("Grant permissions, then press Start relay again.");
            return;
        }
        Intent request=new Intent(activity,RelayService.class).setAction("start")
            .putExtra("output",out).putExtra("input",in).putExtra("microphone",microphone.isChecked());
        try { activity.startForegroundService(request); }
        catch (RuntimeException error) { state.setText("Cannot start relay: "+error.getMessage()); }
    }
}
