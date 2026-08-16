package com.xiangqi.click

import android.app.Activity
import android.os.Bundle
import android.widget.TextView
import android.widget.LinearLayout
import android.graphics.Color

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val tv = TextView(this).apply {
            text = "ClickServer 无障碍点击服务\n\n" +
                    "HTTP: http://127.0.0.1:8123\n" +
                    "接口: POST /tap  POST /swipe  GET /health\n\n" +
                    "使用前请在 系统设置 → 无障碍 → ClickServer 中开启。"
            textSize = 16f
            setPadding(48, 48, 48, 48)
            setTextColor(Color.BLACK)
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(tv)
        }
        setContentView(root)
    }
}
