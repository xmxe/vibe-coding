package com.github.fq.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface DataItemDao {
    @Query("SELECT result FROM data_items WHERE keyword LIKE '%' || :query || '%' LIMIT 1")
    suspend fun searchResult(query: String): String?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(item: DataItem)

    @Query("DELETE FROM data_items")
    suspend fun deleteAll()
}