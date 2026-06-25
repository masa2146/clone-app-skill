package com.example

@Entity(tableName = "users")
data class UserEntity(val id: Long, val email: String)
