package com.github.fq

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.appcompat.widget.SwitchCompat
import com.github.fq.database.DatabaseInitializer

class MainActivity : AppCompatActivity() {

    private lateinit var switchAccessibilityMonitor: SwitchCompat
    private lateinit var btnCheckOverlay: Button

    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (Settings.canDrawOverlays(this)) {
                Toast.makeText(applicationContext, "已获得悬浮窗权限", Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(applicationContext, "未获得悬浮窗权限", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private val usageAccessLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (hasUsageAccess()) {
            Toast.makeText(applicationContext, "已获得“使用情况访问”权限", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(applicationContext, "未获得“使用情况访问权限“，部分功能受限", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 初始化数据库
        DatabaseInitializer.initializeDatabase(this)
        setContentView(R.layout.activity_main)

        switchAccessibilityMonitor = findViewById(R.id.switchAccessibilityMonitor)
        btnCheckOverlay = findViewById(R.id.btnCheckOverlay)

        // 初始化 Switch 状态
        val sp = getSharedPreferences("config", Context.MODE_PRIVATE)
        switchAccessibilityMonitor.isChecked = sp.getBoolean("enable_float_window", false)

        switchAccessibilityMonitor.setOnClickListener {
            if (!MyAccessibilityService.isAccessibilityEnabled(this)) {
                openAccessibilitySettings()
                // 稍后会自动检查状态
            }
        }
        // 共享开关状态
        switchAccessibilityMonitor.setOnCheckedChangeListener { _, isChecked ->
            sp.edit().putBoolean("enable_float_window", isChecked).apply()
            if (!isChecked) {
                FloatWindowManager.hideWindow()
            }
        }

        btnCheckOverlay.setOnClickListener {
            checkOverlayPermission()
        }

        // findViewById<Button>(R.id.btnGrantUsageAccess).setOnClickListener {
        //     openUsageAccessSettings()
        // }

    }

    private fun openAccessibilitySettings() {
        try {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "无法打开无障碍设置", Toast.LENGTH_SHORT).show()
        }
    }

    private fun checkOverlayPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (!Settings.canDrawOverlays(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:$packageName")
                )
                overlayPermissionLauncher.launch(intent)
                // startActivityForResult(intent, REQUEST_CODE_OVERLAY)
            } else {
                Toast.makeText(this, "已获得悬浮窗权限", Toast.LENGTH_SHORT).show()
            }
        } else {
            Toast.makeText(this, "无需手动授权悬浮窗", Toast.LENGTH_SHORT).show()
        }
    }

    private fun openUsageAccessSettings() {
        try {
            val intent = Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            usageAccessLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "无法打开“使用情况访问”设置，请手动在权限中开启", Toast.LENGTH_LONG).show()
        }
    }

    private fun hasUsageAccess(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.LOLLIPOP) return true

        val usageStatsManager = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val endTime = System.currentTimeMillis()
        val beginTime = endTime - 1000 * 60 // 1分钟内
        val usageStats = usageStatsManager.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY,
            beginTime,
            endTime
        )
        return usageStats != null && usageStats.isNotEmpty()
    }

    override fun onDestroy() {
        super.onDestroy()
        if (isFinishing) {
            FloatWindowManager.hideWindow()
        }
    }

    override fun onResume() {
        super.onResume()
        syncSwitchWithAccessibilityState()
    }

    /**
     * 开关与无障碍权限状态同步
     */
    private fun syncSwitchWithAccessibilityState() {
        val isEnabled = MyAccessibilityService.isAccessibilityEnabled(this)
        val sp = getSharedPreferences("config", Context.MODE_PRIVATE)
        val floatWindowEnabled = sp.getBoolean("enable_float_window", false)

        if (!isEnabled) {
            if (switchAccessibilityMonitor.isChecked) {
                switchAccessibilityMonitor.isChecked = false
            }
            if (floatWindowEnabled) {
                sp.edit().putBoolean("enable_float_window", false).apply()
            }
            FloatWindowManager.hideWindow()
            Toast.makeText(this, "无障碍服务已关闭，功能已停用", Toast.LENGTH_SHORT).show()
        } else {
            switchAccessibilityMonitor.isChecked = floatWindowEnabled
        }
    }
}