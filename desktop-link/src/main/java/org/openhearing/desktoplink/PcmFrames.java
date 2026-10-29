// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.desktoplink;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

/** PassThrough v1 mono PCM16LE frame encoding. */
public final class PcmFrames {
    public static final int SAMPLE_RATE = 32000;
    public static final int MAX_BYTES = 12800;
    private PcmFrames() { }

    public static byte[] read(DataInputStream input) throws IOException {
        int first = input.read();
        if (first < 0) return null;
        byte[] rest = new byte[3];
        input.readFully(rest);
        int length = (first << 24) | ((rest[0] & 255) << 16) | ((rest[1] & 255) << 8) | (rest[2] & 255);
        if (length <= 0 || length > MAX_BYTES || (length & 1) != 0) throw new IOException("Invalid PCM frame length");
        byte[] data = new byte[length];
        input.readFully(data);
        return data;
    }

    public static void write(DataOutputStream output, byte[] data, int count) throws IOException {
        if (count <= 0 || count > MAX_BYTES || count > data.length || (count & 1) != 0)
            throw new IOException("Invalid PCM frame length");
        byte[] frame = new byte[count + 4];
        frame[0] = (byte) (count >>> 24);
        frame[1] = (byte) (count >>> 16);
        frame[2] = (byte) (count >>> 8);
        frame[3] = (byte) count;
        System.arraycopy(data, 0, frame, 4, count);
        output.write(frame);
        output.flush();
    }
}
