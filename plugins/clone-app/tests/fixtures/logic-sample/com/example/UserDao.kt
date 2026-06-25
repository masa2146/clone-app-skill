package com.example

@Dao
interface UserDao {
    @Query("SELECT * FROM users")
    fun all(): List<UserEntity>
}
