package com.motionrunner.companion

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.motionrunner.companion.accessibility.MotionRunnerAccessibilityService
import com.motionrunner.companion.network.CompanionConnectionService

class MainActivity : AppCompatActivity() {
    private lateinit var status: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        status = TextView(this)
        val accessibility = Button(this).apply {
            text = "Open Accessibility settings"
            setOnClickListener { startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)) }
        }
        val connect = Button(this).apply {
            text = "Start companion connection"
            setOnClickListener { CompanionConnectionService.start(this@MainActivity); refresh(status) }
        }
        setContentView(LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 72, 48, 48)
            addView(status)
            addView(accessibility)
            addView(connect)
        })
        refresh(status)
    }

    override fun onResume() {
        super.onResume()
        refresh(status)
    }

    private fun refresh(status: TextView) {
        status.text = buildString {
            append("MotionRunner Android Companion\n\n")
            append("Accessibility: ")
            append(if (MotionRunnerAccessibilityService.isAvailable()) "enabled" else "disabled")
            append("\nEndpoint: ")
            append(getSharedPreferences(CompanionConnectionService.PREFERENCES, MODE_PRIVATE)
                .getString(CompanionConnectionService.KEY_ENDPOINT, CompanionConnectionService.DEFAULT_ENDPOINT))
        }
    }
}
