package com.motionrunner.companion.accessibility

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import com.motionrunner.companion.protocol.TouchCommand

class MotionRunnerAccessibilityService : AccessibilityService() {
    private val scheduler by lazy { GestureSegmentScheduler(this) }

    override fun onServiceConnected() {
        super.onServiceConnected()
        service = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        scheduler.cancelAll("service_destroyed")
        service = null
        super.onDestroy()
    }

    fun dispatch(command: TouchCommand, onResult: (Boolean, String?) -> Unit) {
        scheduler.submit(command, onResult)
    }

    companion object {
        @Volatile private var service: MotionRunnerAccessibilityService? = null

        fun isAvailable(): Boolean = service != null

        fun dispatch(command: TouchCommand, onResult: (Boolean, String?) -> Unit) {
            val current = service
            if (current == null) onResult(false, "Accessibility service is disabled")
            else current.dispatch(command, onResult)
        }
    }
}
