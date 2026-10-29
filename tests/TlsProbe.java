// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

public final class TlsProbe {
    public static void main(String[] args) throws Exception {
        try (PinnedConnection connection=new PinnedConnection("127.0.0.1",Integer.parseInt(args[0]),args[1],args[2])) {
            byte[] payload=FrameCodec.read(connection.input);
            if (payload==null || payload.length!=4) throw new AssertionError("Missing desktop frame");
            FrameCodec.write(connection.output,payload,payload.length);
        }
    }
}
