// SPDX-License-Identifier: GPL-3.0-only
package org.openhearing.app;

import android.media.AudioDeviceInfo;
import android.os.Build;

final class HearingRoutes {
    private HearingRoutes() { }
    // API 37 introduced TYPE_BLE_HEARING_AID (33). Keep compileSdk35 compatibility.
    // https://developer.android.com/reference/android/media/AudioDeviceInfo#TYPE_BLE_HEARING_AID
    static boolean isLeHearingDevice(int type) {
        return type==AudioDeviceInfo.TYPE_BLE_HEADSET || (Build.VERSION.SDK_INT>=37 && type==33);
    }
    static boolean isOutput(int type) {
        return isLeHearingDevice(type) || type==AudioDeviceInfo.TYPE_HEARING_AID;
    }
}
