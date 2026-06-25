package com.example

class SyncUseCase(private val repo: UserDao) {
    suspend operator fun invoke() = repo.all()
}
