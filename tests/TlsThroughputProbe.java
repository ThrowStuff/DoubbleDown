// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.desktoplink;

/** Sustained simultaneous PCM using the actual Android transport sources. */
public final class TlsThroughputProbe {
    public static void main(String[] args) throws Exception {
        try (DesktopLinkSession connection=new DesktopLinkSession("127.0.0.1",Integer.parseInt(args[0]),args[1],args[2])) {
            Thread sender=new Thread(() -> {
                try {
                    byte[] pcm=new byte[1280];
                    for (int i=0;i<200;i++) {
                        connection.writeFrame(pcm,pcm.length);
                        Thread.sleep(20);
                    }
                } catch (Exception error) { throw new RuntimeException(error); }
            });
            sender.setDaemon(true);
            sender.start();
            long deadline=System.nanoTime()+4_700_000_000L;
            int received=0;
            while (System.nanoTime()<deadline && connection.readFrame()!=null) received++;
            System.out.println("downlink_frames="+received);
        }
    }
}
