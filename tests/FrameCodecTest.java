// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.desktoplink;

import java.io.*;
import java.util.Arrays;

public final class FrameCodecTest {
    public static void main(String[] args) throws Exception {
        byte[] pcm = {0, 0, -1, 127, 0, -128};
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        PcmFrames.write(new DataOutputStream(bytes), pcm, pcm.length);
        byte[] wire = bytes.toByteArray();
        if (!Arrays.equals(Arrays.copyOf(wire, 4), new byte[]{0,0,0,6})) throw new AssertionError("Length byte order");
        DataInputStream input = new DataInputStream(new ByteArrayInputStream(wire));
        if (!Arrays.equals(pcm, PcmFrames.read(input))) throw new AssertionError("PCM payload changed");
        if (PcmFrames.read(input) != null) throw new AssertionError("Clean EOF");
        for (int invalid : new int[]{0, 1, 3, 12802, -1, Integer.MAX_VALUE}) {
            ByteArrayOutputStream bad = new ByteArrayOutputStream();
            new DataOutputStream(bad).writeInt(invalid);
            expectFailure(bad.toByteArray());
        }
        expectFailure(new byte[]{0,0});
        expectFailure(new byte[]{0,0,0,4,1,2});
        byte[] maximum = new byte[PcmFrames.MAX_BYTES];
        bytes.reset();
        PcmFrames.write(new DataOutputStream(bytes), maximum, maximum.length);
        if (PcmFrames.read(new DataInputStream(new ByteArrayInputStream(bytes.toByteArray()))).length != maximum.length) throw new AssertionError();
        System.out.println("PASS: frame byte order, payload preservation, EOF, bounds and truncation");
    }
    private static void expectFailure(byte[] wire) throws Exception {
        try {
            PcmFrames.read(new DataInputStream(new ByteArrayInputStream(wire)));
            throw new AssertionError("Accepted invalid frame");
        } catch (IOException expected) { }
    }
}
