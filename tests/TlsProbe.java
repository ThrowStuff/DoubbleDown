// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.desktoplink;

public final class TlsProbe {
    public static void main(String[] args) throws Exception {
        try (DesktopLinkSession connection=new DesktopLinkSession("127.0.0.1",Integer.parseInt(args[0]),args[1],args[2])) {
            byte[] payload=connection.readFrame();
            if (payload==null || payload.length!=4) throw new AssertionError("Missing desktop frame");
            connection.writeFrame(payload,payload.length);
        }
    }
}
