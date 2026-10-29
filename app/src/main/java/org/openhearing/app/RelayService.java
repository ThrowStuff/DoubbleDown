// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

import android.app.*;
import android.Manifest;
import android.content.*;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.media.*;
import android.os.*;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/** User-started duplex relay. No fallback to phone speaker or phone microphone. */
public final class RelayService extends Service {
    public static volatile String status = "Not connected";
    private final AtomicBoolean running = new AtomicBoolean(false);
    private volatile PinnedConnection connection;
    private volatile AudioRecord recorder;
    private volatile AudioTrack player;
    private volatile Thread worker;
    private AudioManager manager;
    private int previousMode;
    private AudioDeviceInfo previousCommunication;
    private boolean changedCommunication;
    private volatile int selectedOutput=-1;
    private volatile int selectedInput=-1;
    private volatile boolean microphoneVerified;
    private volatile boolean playbackVerified;
    private final AtomicLong inputRouteEpoch=new AtomicLong();
    private AudioFocusRequest focus;
    private final AudioDeviceCallback devices=new AudioDeviceCallback() {
        @Override public void onAudioDevicesRemoved(AudioDeviceInfo[] removed) {
            for (AudioDeviceInfo device:removed) if (device.getId()==selectedOutput || device.getId()==selectedInput) {
                stopRelay("Stopped: selected hearing device disconnected");
            }
        }
    };

    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onCreate() {
        super.onCreate();
        manager = getSystemService(AudioManager.class);
        getSystemService(NotificationManager.class).createNotificationChannel(
            new NotificationChannel("relay", "Audio relay", NotificationManager.IMPORTANCE_LOW));
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null || "stop".equals(intent.getAction())) {
            stopRelay("Stopped");
            if (worker==null || !worker.isAlive()) stopSelfResult(startId);
            return START_NOT_STICKY;
        }
        if (worker!=null && worker.isAlive()) return START_NOT_STICKY;
        if (!running.compareAndSet(false,true)) return START_NOT_STICKY;
        boolean microphone = intent.getBooleanExtra("microphone", false);
        if ((Build.VERSION.SDK_INT>=31 && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)!=PackageManager.PERMISSION_GRANTED) ||
            (microphone && checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)) {
            running.set(false);
            status="Stopped: required permission is missing";
            stopSelfResult(startId);
            return START_NOT_STICKY;
        }
        Intent stop = new Intent(this,RelayService.class).setAction("stop");
        PendingIntent stopAction = PendingIntent.getService(this,0,stop,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent open = PendingIntent.getActivity(this,1,new Intent(this,MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notification = new Notification.Builder(this,"relay")
            .setContentTitle("PassThrough")
            .setContentText(microphone ? "Audio relay with selected hearing-device microphone" : "Playback relay")
            .setSmallIcon(android.R.drawable.stat_sys_headset).setContentIntent(open)
            .addAction(new Notification.Action.Builder(null,"Stop",stopAction).build())
            .setOngoing(true).build();
        int types = ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK;
        if (microphone) types |= ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE;
        try {
            if (Build.VERSION.SDK_INT>=29) startForeground(1,notification,types);
            else startForeground(1,notification);
        }
        catch (RuntimeException error) {
            running.set(false);
            status="Stopped: Android refused foreground relay: "+error.getMessage();
            stopSelfResult(startId);
            return START_NOT_STICKY;
        }
        status = "Connecting…";
        worker = new Thread(() -> runRelay(intent,microphone),"passthrough-relay");
        worker.start();
        return START_NOT_STICKY;
    }

    private AudioDeviceInfo findDevice(int id, int direction) throws IOException {
        for (AudioDeviceInfo device : manager.getDevices(direction)) {
            if (device.getId()==id && (direction==AudioManager.GET_DEVICES_INPUTS ?
                HearingRoutes.isLeHearingDevice(device.getType()) : HearingRoutes.isOutput(device.getType()))) return device;
        }
        throw new IOException("Selected hearing-device route is unavailable");
    }

    private void runRelay(Intent request, boolean microphone) {
        Thread uplink = null;
        try {
            AudioDeviceInfo output = findDevice(request.getIntExtra("output",-1),AudioManager.GET_DEVICES_OUTPUTS);
            AudioDeviceInfo input = microphone ? findDevice(request.getIntExtra("input",-1),AudioManager.GET_DEVICES_INPUTS) : null;
            selectedOutput=output.getId(); selectedInput=input==null ? -1 : input.getId();
            microphoneVerified=false; playbackVerified=false;
            manager.registerAudioDeviceCallback(devices,new Handler(Looper.getMainLooper()));
            SharedPreferences config = getSharedPreferences("connection",MODE_PRIVATE);
            int mode = config.getInt("transport",0);
            if (mode==0) throw new IOException("Bluetooth computer relay is not implemented yet");
            String host = config.getString("host","").trim();
            if (mode==2 && config.getInt("usbMode",0)==1) host="127.0.0.1";
            int port = Integer.parseInt(config.getString("port","49721"));
            if (port<1 || port>65535 || host.isEmpty()) throw new IOException("Configure the computer address and port first");
            PinnedConnection established = new PinnedConnection(host,port,
                config.getString("fingerprint",""),config.getString("token",""));
            connection = established;
            if (!running.get()) { established.close(); return; }
            if (microphone) {
                if (Build.VERSION.SDK_INT<31) throw new IOException("Microphone communication routing requires Android12 or newer");
                previousMode = manager.getMode();
                previousCommunication = manager.getCommunicationDevice();
                if (previousMode!=AudioManager.MODE_NORMAL) throw new IOException("Another communication session is active");
                manager.setMode(AudioManager.MODE_IN_COMMUNICATION);
                changedCommunication = true;
                if (!manager.setCommunicationDevice(output)) throw new IOException("Android rejected the selected communication route");
            }
            AudioAttributes attributes = new AudioAttributes.Builder()
                .setUsage(microphone ? AudioAttributes.USAGE_VOICE_COMMUNICATION : AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
            focus=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                .setAudioAttributes(attributes)
                .setOnAudioFocusChangeListener(change -> {
                    if (change!=AudioManager.AUDIOFOCUS_GAIN) stopRelay("Stopped: another app needs audio");
                },new Handler(Looper.getMainLooper())).build();
            if (manager.requestAudioFocus(focus)!=AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
                throw new IOException("Android did not grant audio focus");
            }
            AudioFormat outputFormat = new AudioFormat.Builder().setSampleRate(FrameCodec.SAMPLE_RATE)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build();
            int playbackMinimum = AudioTrack.getMinBufferSize(FrameCodec.SAMPLE_RATE,
                AudioFormat.CHANNEL_OUT_MONO,AudioFormat.ENCODING_PCM_16BIT);
            if (playbackMinimum<=0) throw new IOException("Requested playback format is unavailable");
            player = new AudioTrack.Builder().setAudioAttributes(attributes).setAudioFormat(outputFormat)
                .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(Math.max(playbackMinimum,6400)).build();
            if (!player.setPreferredDevice(output)) throw new IOException("Selected output route was rejected");
            player.setVolume(0f); // prime and verify the actual route before making playback audible
            player.addOnRoutingChangedListener(router -> {
                AudioDeviceInfo actual = player == null ? null : player.getRoutedDevice();
                if ((actual!=null && actual.getId()!=output.getId()) || (playbackVerified && actual==null)) {
                    if (player!=null) player.setVolume(0f);
                    stopRelay("Stopped: playback route changed");
                }
            },new Handler(Looper.getMainLooper()));
            player.play();
            if (microphone) {
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED) {
                    throw new SecurityException("Microphone permission was revoked");
                }
                int captureMinimum = AudioRecord.getMinBufferSize(FrameCodec.SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO,AudioFormat.ENCODING_PCM_16BIT);
                if (captureMinimum<=0) throw new IOException("Requested microphone format is unavailable");
                recorder = new AudioRecord.Builder().setAudioSource(MediaRecorder.AudioSource.VOICE_COMMUNICATION)
                    .setAudioFormat(new AudioFormat.Builder().setSampleRate(FrameCodec.SAMPLE_RATE)
                        .setChannelMask(AudioFormat.CHANNEL_IN_MONO).setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                    .setBufferSizeInBytes(Math.max(captureMinimum,6400)).build();
                if (!recorder.setPreferredDevice(input)) throw new IOException("Selected microphone route was rejected");
                recorder.addOnRoutingChangedListener(router -> {
                    inputRouteEpoch.incrementAndGet();
                    AudioRecord active=recorder;
                    AudioDeviceInfo actual=active==null ? null : active.getRoutedDevice();
                    if (microphoneVerified && (actual==null || actual.getId()!=selectedInput)) {
                        stopRelay("Stopped: selected microphone route changed");
                    }
                },new Handler(Looper.getMainLooper()));
                recorder.startRecording();
                final int inputId = input.getId();
                uplink = new Thread(() -> sendMicrophone(inputId),"passthrough-microphone");
                uplink.start();
            }
            status = microphone ? "Connected · checking microphone route" : "Connected · playback only";
            boolean outputVerified=false;
            long outputDeadline=SystemClock.elapsedRealtime()+3000;
            while (running.get()) {
                byte[] pcm = FrameCodec.read(established.input);
                if (pcm==null) throw new IOException("Desktop disconnected");
                AudioDeviceInfo actual = player.getRoutedDevice();
                if (outputVerified && (actual==null || actual.getId()!=output.getId())) throw new IOException("Selected playback route is not active");
                int offset=0;
                while (running.get() && offset<pcm.length) {
                    int written = player.write(pcm,offset,pcm.length-offset,AudioTrack.WRITE_BLOCKING);
                    if (written<=0) throw new IOException("Playback stopped");
                    offset+=written;
                }
                if (!outputVerified) {
                    actual=player.getRoutedDevice();
                    if (actual!=null && actual.getId()==output.getId()) {
                        outputVerified=true;
                        playbackVerified=true;
                        player.setVolume(1f);
                    } else if (actual!=null || SystemClock.elapsedRealtime()>outputDeadline) {
                        throw new IOException("Selected playback route is not active");
                    }
                }
            }
        } catch (Exception error) {
            if (running.get()) status = "Stopped: " + error.getMessage();
        } finally {
            running.set(false);
            closeConnection();
            if (recorder!=null) { try { recorder.stop(); } catch (IllegalStateException ignored) { } }
            if (uplink!=null) {
                try { uplink.join(1500); } catch (InterruptedException ignored) { Thread.currentThread().interrupt(); }
            }
            if (recorder!=null) { try { recorder.release(); } catch (RuntimeException ignored) { } recorder=null; }
            if (player!=null) { try { player.release(); } catch (RuntimeException ignored) { } player=null; }
            try { if (changedCommunication && Build.VERSION.SDK_INT>=31) {
                if (manager.getMode()==AudioManager.MODE_IN_COMMUNICATION) {
                    AudioDeviceInfo current=manager.getCommunicationDevice();
                    if (current!=null && current.getId()==selectedOutput) {
                        if (previousCommunication==null) manager.clearCommunicationDevice();
                        else manager.setCommunicationDevice(previousCommunication);
                        manager.setMode(previousMode);
                    }
                }
                changedCommunication=false;
            } } catch (RuntimeException ignored) { }
            try { manager.unregisterAudioDeviceCallback(devices); } catch (RuntimeException ignored) { }
            try { if (focus!=null) manager.abandonAudioFocusRequest(focus); } catch (RuntimeException ignored) { }
            focus=null;
            try { stopForeground(STOP_FOREGROUND_REMOVE); } finally { stopSelf(); }
        }
    }

    private void sendMicrophone(int selectedId) {
        byte[] pcm = new byte[1280];
        long deadline=SystemClock.elapsedRealtime()+2000;
        try {
            while (running.get()) {
                long epoch=inputRouteEpoch.get();
                AudioDeviceInfo before=recorder.getRoutedDevice();
                int count=recorder.read(pcm,0,pcm.length,AudioRecord.READ_BLOCKING);
                if (count<=0) throw new IOException("Microphone capture stopped");
                AudioDeviceInfo actual=recorder.getRoutedDevice();
                if (before==null || before.getId()!=selectedId || actual==null || actual.getId()!=selectedId || epoch!=inputRouteEpoch.get()) {
                    if (microphoneVerified) throw new IOException("Selected hearing-device microphone route changed");
                    if (SystemClock.elapsedRealtime()<deadline) continue; // discard every unverified sample
                    throw new IOException("Selected hearing-device microphone is not the actual recording source");
                }
                deadline=0;
                microphoneVerified=true;
                FrameCodec.write(connection.output,pcm,count);
                status="Connected · selected microphone route verified by Android";
            }
        } catch (Exception error) {
            if (running.get()) stopRelay("Stopped: " + error.getMessage());
        }
    }

    private void closeConnection() {
        PinnedConnection active=connection;
        connection=null;
        if (active!=null) try { active.close(); } catch (IOException ignored) { }
    }
    private void stopRelay(String reason) {
        status=reason;
        running.set(false);
        closeConnection();
        AudioTrack activePlayer=player;
        if (activePlayer!=null) {
            try { activePlayer.setVolume(0f); activePlayer.pause(); activePlayer.flush(); }
            catch (IllegalStateException ignored) { }
        }
        AudioRecord activeRecorder=recorder;
        if (activeRecorder!=null) {
            try { activeRecorder.stop(); } catch (IllegalStateException ignored) { }
        }
    }
    @Override public void onDestroy() {
        stopRelay(status.startsWith("Stopped") ? status : "Stopped");
        super.onDestroy();
    }
}
