package com.github.fq.database

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "data_items")
data class DataItem(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val keyword: String,      // 用于搜索的关键词
    val result: String        // 返回的结果
)