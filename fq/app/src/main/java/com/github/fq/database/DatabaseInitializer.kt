package com.github.fq.database

import android.content.Context
import java.io.FileOutputStream
import java.io.IOException

object DatabaseInitializer {

    private const val DB_NAME = "data.db"

    fun initializeDatabase(context: Context) {
        val dbFile = context.getDatabasePath(DB_NAME)
        if (!dbFile.exists()) {
            try {
                dbFile.parentFile?.mkdirs()
                val inputStream = context.assets.open(DB_NAME)
                val outputStream = FileOutputStream(dbFile)
                inputStream.copyTo(outputStream)
                inputStream.close()
                outputStream.close()
            } catch (e: IOException) {
                e.printStackTrace()
            }
        }

        // 使用预置的数据库路径
        AppDatabase.getDatabase(context)
    }
}