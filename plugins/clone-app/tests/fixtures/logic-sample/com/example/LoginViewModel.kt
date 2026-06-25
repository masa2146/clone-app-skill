package com.example

class LoginViewModel : ViewModel() {
    fun validate(email: String): Boolean {
        return email.matches(Regex("^[^@]+@[^@]+$"))
    }
}
