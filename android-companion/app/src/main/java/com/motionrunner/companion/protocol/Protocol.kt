package com.motionrunner.companion.protocol

import org.json.JSONArray
import org.json.JSONObject

const val PROTOCOL_VERSION = 1

enum class MessageType { HELLO, DEVICE_INFO, TOUCH_COMMAND, ACK, HEARTBEAT, ERROR }

data class ProtocolEnvelope(
    val protocolVersion: Int,
    val messageType: MessageType,
    val sequenceNumber: Long,
    val timestamp: Double,
    val payload: JSONObject,
)

data class TouchCommand(
    val commandType: String,
    val pointerId: Int,
    val x: Float,
    val y: Float,
    val commandTimestamp: Double,
    val commandSequence: Long,
    val confidence: Float,
    val correlationId: String,
    val reason: String,
)

object ProtocolCodec {
    fun decode(raw: String): ProtocolEnvelope {
        val json = JSONObject(raw)
        val required = listOf("protocolVersion", "messageType", "sequenceNumber", "timestamp", "payload")
        require(required.all(json::has)) { "Missing required protocol field" }
        val payload = json.getJSONObject("payload")
        return ProtocolEnvelope(
            protocolVersion = json.getInt("protocolVersion"),
            messageType = MessageType.valueOf(json.getString("messageType")),
            sequenceNumber = json.getLong("sequenceNumber"),
            timestamp = json.getDouble("timestamp"),
            payload = payload,
        ).also {
            require(it.protocolVersion == PROTOCOL_VERSION) { "Unsupported protocol version ${it.protocolVersion}" }
            require(it.sequenceNumber >= 0) { "Negative sequence number" }
        }
    }

    fun encode(envelope: ProtocolEnvelope): String = JSONObject().apply {
        put("protocolVersion", envelope.protocolVersion)
        put("messageType", envelope.messageType.name)
        put("sequenceNumber", envelope.sequenceNumber)
        put("timestamp", envelope.timestamp)
        put("payload", envelope.payload)
    }.toString()

    fun touchCommand(payload: JSONObject): TouchCommand = TouchCommand(
        commandType = payload.getString("commandType"),
        pointerId = payload.getInt("pointerId"),
        x = payload.getDouble("x").toFloat(),
        y = payload.getDouble("y").toFloat(),
        commandTimestamp = payload.getDouble("commandTimestamp"),
        commandSequence = payload.getLong("commandSequence"),
        confidence = payload.optDouble("confidence", 1.0).toFloat(),
        correlationId = payload.optString("correlationId", ""),
        reason = payload.optString("reason", ""),
    )

    fun intArray(values: Collection<Int>): JSONArray = JSONArray(values)
}
