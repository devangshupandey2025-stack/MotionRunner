package com.motionrunner.companion.accessibility

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.motionrunner.companion.protocol.TouchCommand
import java.util.ArrayDeque

/** Serializes one-pointer continued gesture segments; competing dispatches are never issued. */
class GestureSegmentScheduler(private val service: AccessibilityService) {
    private data class Queued(val command: TouchCommand, val callback: (Boolean, String?) -> Unit)
    private val handler = Handler(Looper.getMainLooper())
    private val queue = ArrayDeque<Queued>()
    private var dispatching = false
    private var active = false
    private var cancelAfterCurrent = false
    private var lastX = 0f
    private var lastY = 0f
    private var previousStroke: GestureDescription.StrokeDescription? = null

    fun submit(command: TouchCommand, callback: (Boolean, String?) -> Unit) {
        handler.post {
            Log.d(TAG, "Queued touch command type=${command.commandType} seq=${command.commandSequence} x=${command.x} y=${command.y}")
            queue.addLast(Queued(command, callback))
            dispatchNext()
        }
    }

    fun cancelAll(reason: String) {
        handler.post {
            Log.w(TAG, "Cancelling touch queue: $reason")
            while (queue.isNotEmpty()) queue.removeFirst().callback(false, reason)
            if (active && dispatching) cancelAfterCurrent = true
            else if (active) finishAtLastPosition(reason)
        }
    }

    private fun dispatchNext() {
        if (dispatching || queue.isEmpty()) return
        val queued = queue.removeFirst()
        val command = queued.command
        if (command.commandType == "CANCEL_ALL") { cancelAll("host_cancel_all"); queued.callback(true, null); return }
        if (command.pointerId != 0) { reject(queued, "Only pointer 0 is supported"); return }
        if (command.commandType == "BEGIN" && active) { reject(queued, "Pointer already active"); return }
        if (command.commandType != "BEGIN" && !active) { reject(queued, "Pointer is not active"); return }
        val finalSegment = command.commandType == "END"
        val path = Path().apply {
            moveTo(if (active) lastX else command.x, if (active) lastY else command.y)
            lineTo(command.x, command.y)
        }
        val stroke = if (previousStroke == null) {
            GestureDescription.StrokeDescription(path, 0, SEGMENT_DURATION_MS, !finalSegment)
        } else {
            previousStroke!!.continueStroke(path, 0, SEGMENT_DURATION_MS, !finalSegment)
        }
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        dispatching = true
        Log.d(TAG, "Dispatching gesture segment type=${command.commandType} final=$finalSegment")
        if (!service.dispatchGesture(gesture, object : AccessibilityService.GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    dispatching = false
                    active = !finalSegment
                    lastX = command.x; lastY = command.y
                    previousStroke = if (finalSegment) null else stroke
                    Log.d(TAG, "Gesture segment completed type=${command.commandType}")
                    queued.callback(true, null)
                    if (cancelAfterCurrent && active) {
                        cancelAfterCurrent = false
                        finishAtLastPosition("cancel_after_inflight_segment")
                    }
                    dispatchNext()
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    dispatching = false; active = false; previousStroke = null; cancelAfterCurrent = false
                    Log.w(TAG, "Android cancelled gesture segment type=${command.commandType}")
                    queued.callback(false, "Android cancelled gesture segment")
                    dispatchNext()
                }
            }, handler)) {
            dispatching = false; active = false; previousStroke = null; cancelAfterCurrent = false
            Log.e(TAG, "Android rejected gesture segment type=${command.commandType}")
            queued.callback(false, "Android rejected gesture segment")
            dispatchNext()
        }
    }

    private fun reject(queued: Queued, reason: String) {
        Log.w(TAG, "Rejected touch command type=${queued.command.commandType}: $reason")
        queued.callback(false, reason)
        dispatchNext()
    }

    private fun finishAtLastPosition(reason: String) {
        submit(TouchCommand("END", 0, lastX, lastY, 0.0, 0, 1f, "", reason)) { _, _ -> }
    }

    private companion object {
        const val SEGMENT_DURATION_MS = 24L
        const val TAG = "MotionRunner"
    }
}
