// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.desktoplink;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** Authenticated, certificate-pinned connection to the desktop-link peer. */
public final class DesktopLinkSession implements AutoCloseable {
    private final SSLSocket socket;
    private final DataInputStream input;
    private final DataOutputStream output;

    public DesktopLinkSession(String host, int port, String fingerprint, String token) throws Exception {
        String pin = fingerprint.replace(":", "").trim().toLowerCase(java.util.Locale.ROOT);
        if (!pin.matches("[0-9a-f]{64}") || !token.matches("[0-9a-f]{64}"))
            throw new IOException("Enter the desktop certificate fingerprint and session token (64 hexadecimal characters each)");
        byte[] expected = new byte[32];
        for (int i = 0; i < 32; i++) expected[i] = (byte) Integer.parseInt(pin.substring(i * 2, i * 2 + 2), 16);
        SSLContext tls = SSLContext.getInstance("TLS");
        tls.init(null, new TrustManager[]{new X509TrustManager() {
            @Override public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            @Override public void checkClientTrusted(X509Certificate[] chain, String auth) throws CertificateException {
                throw new CertificateException("Client certificates are not used");
            }
            @Override public void checkServerTrusted(X509Certificate[] chain, String auth) throws CertificateException {
                try {
                    if (chain == null || chain.length == 0) throw new CertificateException("Missing server certificate");
                    chain[0].checkValidity();
                    byte[] actual = MessageDigest.getInstance("SHA-256").digest(chain[0].getEncoded());
                    if (!MessageDigest.isEqual(expected, actual)) throw new CertificateException("Desktop certificate fingerprint does not match");
                } catch (CertificateException error) { throw error; }
                catch (Exception error) { throw new CertificateException(error); }
            }
        }}, new SecureRandom());
        Socket raw = new Socket();
        SSLSocket secure = null;
        try {
            raw.setTcpNoDelay(true);
            raw.connect(new InetSocketAddress(host, port), 5000);
            raw.setSoTimeout(5000);
            secure = (SSLSocket) tls.getSocketFactory().createSocket(raw, host, port, true);
            java.util.List<String> supported = java.util.Arrays.asList(secure.getSupportedProtocols());
            java.util.ArrayList<String> protocols = new java.util.ArrayList<>();
            if (supported.contains("TLSv1.3")) protocols.add("TLSv1.3");
            if (supported.contains("TLSv1.2")) protocols.add("TLSv1.2");
            if (protocols.isEmpty()) throw new IOException("TLS1.2 or newer is required");
            secure.setEnabledProtocols(protocols.toArray(new String[0]));
            secure.setSoTimeout(5000);
            secure.startHandshake();
            DataOutputStream out = new DataOutputStream(secure.getOutputStream());
            DataInputStream in = new DataInputStream(secure.getInputStream());
            out.write("PTHRU001".getBytes(StandardCharsets.US_ASCII));
            out.write(token.getBytes(StandardCharsets.US_ASCII));
            out.flush();
            byte[] reply = new byte[4];
            in.readFully(reply);
            if (!java.util.Arrays.equals(reply, "OKAY".getBytes(StandardCharsets.US_ASCII)))
                throw new IOException("Desktop authentication rejected");
            socket = secure;
            input = in;
            output = out;
        } catch (Exception error) {
            if (secure != null) secure.close();
            raw.close();
            throw error;
        }
    }

    public byte[] readFrame() throws IOException { return PcmFrames.read(input); }
    public void writeFrame(byte[] pcm, int count) throws IOException { PcmFrames.write(output, pcm, count); }
    @Override public void close() throws IOException { socket.close(); }
}
