package com.motionrunner.companion.network

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.motionrunner.companion.BuildConfig
import com.motionrunner.companion.R
import com.motionrunner.companion.accessibility.MotionRunnerAccessibilityService
import com.motionrunner.companion.protocol.MessageType
import com.motionrunner.companion.protocol.PROTOCOL_VERSION
import com.motionrunner.companion.protocol.ProtocolCodec
import com.motionrunner.companion.protocol.ProtocolEnvelope
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import org.json.JSONArray
import java.util.concurrent.TimeUnit

/** Owns companion connection/reconnect lifecycle; it contains no Android touch APIs. */
class CompanionConnectionService : Service() {
    private val handler = Handler(Looper.getMainLooper())
    private val client = OkHttpClient.Builder().pingInterval(2, TimeUnit.SECONDS).build()
    private var socket: WebSocket? = null
    private var sequence = 1L
    private var running = false

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        running = true
        createNotificationChannel()
        Log.i(TAG, "Starting companion connection service")
        startForeground(NOTIFICATION_ID, NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(getString(R.string.app_name))
            .setContentText("Waiting for MotionRunner host")
            .setOngoing(true)
            .build())
        connect()
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "Stopping companion connection service")
        running = false
        handler.removeCallbacksAndMessages(null)
        socket?.close(1000, "service stopped")
        client.dispatcher.executorService.shutdown()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun connect() {
        if (!running || socket != null) return
        val endpoint = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
            .getString(KEY_ENDPOINT, DEFAULT_ENDPOINT) ?: DEFAULT_ENDPOINT
        Log.i(TAG, "Connecting to MotionRunner host at $endpoint")
        socket = client.newWebSocket(Request.Builder().url(endpoint).build(), object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected")
                sendHello()
                sendDeviceInfo()
                scheduleHeartbeat()
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val envelope = ProtocolCodec.decode(text)
                    Log.d(TAG, "Received ${envelope.messageType} seq=${envelope.sequenceNumber}")
                    when (envelope.messageType) {
                        MessageType.HELLO -> sendDeviceInfo()
                        MessageType.TOUCH_COMMAND -> dispatchTouch(envelope)
                        MessageType.HEARTBEAT -> sendAck(envelope.sequenceNumber)
                        else -> Unit
                    }
                } catch (exception: Exception) {
                    Log.e(TAG, "Invalid host message", exception)
                    sendError("INVALID_MESSAGE", exception.message ?: "Malformed message")
                }
            }

            override fun onFailure(webSocket: WebSocket, throwable: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket failed: ${throwable.message}")
                reconnectLater()
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WebSocket closed code=$code reason=$reason")
                reconnectLater()
            }
        })
    }

    private fun dispatchTouch(envelope: ProtocolEnvelope) {
        val command = ProtocolCodec.touchCommand(envelope.payload)
        Log.d(TAG, "Dispatching touch command type=${command.commandType} seq=${command.commandSequence}")
        MotionRunnerAccessibilityService.dispatch(command) { accepted, reason ->
            if (accepted) {
                Log.d(TAG, "Touch command accepted seq=${command.commandSequence}")
                sendAck(envelope.sequenceNumber)
            } else {
                Log.w(TAG, "Touch command rejected seq=${command.commandSequence}: $reason")
                sendError("TOUCH_REJECTED", reason ?: "Touch command rejected", envelope.sequenceNumber)
            }
        }
    }

    private fun sendHello() = send(MessageType.HELLO, JSONObject().apply {
        put("companionVersion", BuildConfig.VERSION_NAME)
        put("supportedProtocolVersions", ProtocolCodec.intArray(listOf(PROTOCOL_VERSION)))
    })

    private fun sendDeviceInfo() {
        val metrics = resources.displayMetrics
        val orientation = if (metrics.widthPixels >= metrics.heightPixels) "LANDSCAPE" else "PORTRAIT"
        send(MessageType.DEVICE_INFO, JSONObject().apply {
            put("companionVersion", BuildConfig.VERSION_NAME)
            put("supportedProtocolVersions", ProtocolCodec.intArray(listOf(PROTOCOL_VERSION)))
            put("androidApiLevel", android.os.Build.VERSION.SDK_INT)
            put("widthPx", metrics.widthPixels)
            put("heightPx", metrics.heightPixels)
            put("density", metrics.density.toDouble())
            put("orientation", orientation)
            put("accessibilityEnabled", MotionRunnerAccessibilityService.isAvailable())
            put("supportedFeatures", JSONArray(listOf("single_pointer", "continued_strokes")))
            put("gestureLimitations", JSONArray(listOf("serialized_segments", "24ms_segment_floor")))
        })
    }

    private fun sendAck(acknowledged: Long) = send(MessageType.ACK, JSONObject().put("ackSequenceNumber", acknowledged))

    private fun sendError(code: String, message: String, relatedSequence: Long? = null) = send(MessageType.ERROR, JSONObject().apply {
        put("code", code); put("message", message)
        if (relatedSequence != null) put("relatedSequenceNumber", relatedSequence)
    })

    private fun scheduleHeartbeat() {
        handler.postDelayed(object : Runnable {
            override fun run() {
                if (!running || socket == null) return
                send(MessageType.HEARTBEAT, JSONObject())
                handler.postDelayed(this, HEARTBEAT_MS)
            }
        }, HEARTBEAT_MS)
    }

    private fun send(type: MessageType, payload: JSONObject) {
        socket?.send(ProtocolCodec.encode(ProtocolEnvelope(PROTOCOL_VERSION, type, sequence++, System.nanoTime() / 1_000_000_000.0, payload)))
    }

    private fun reconnectLater() {
        socket = null
        if (running) {
            Log.i(TAG, "Scheduling reconnect in ${RECONNECT_MS}ms")
            handler.postDelayed({ connect() }, RECONNECT_MS)
        }
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL_ID, getString(R.string.connection_channel_name), NotificationManager.IMPORTANCE_LOW))
    }

    companion object {
        const val PREFERENCES = "motionrunner_companion"
        const val KEY_ENDPOINT = "endpoint"
        const val DEFAULT_ENDPOINT = "ws://127.0.0.1:8765"
        private const val CHANNEL_ID = "motionrunner_connection"
        private const val NOTIFICATION_ID = 7
        private const val HEARTBEAT_MS = 1_000L
        private const val RECONNECT_MS = 1_000L
        private const val TAG = "MotionRunner"

        fun start(context: Context): String {
            return try {
                ContextCompat.startForegroundService(context, Intent(context, CompanionConnectionService::class.java))
                "starting"
            } catch (exception: Exception) {
                Log.e(TAG, "Failed to start connection service", exception)
                "failed: ${exception.message ?: exception.javaClass.simpleName}"
            }
        }
    }
}
