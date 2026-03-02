import SwiftUI

// MARK: - Login View

/// Email/password login screen shown before the main app when unauthenticated.
struct LoginView: View {
    @Environment(AuthController.self) private var authController

    @State private var email = ""
    @State private var password = ""
    @State private var isSignUp = false

    var body: some View {
        VStack(spacing: 24) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .font(.system(size: 48))
                    .foregroundStyle(.blue)
                Text("SwiftBolt ML")
                    .font(.largeTitle.bold())
                Text(isSignUp ? "Create an account" : "Sign in to continue")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            // Form
            VStack(spacing: 12) {
                TextField("Email", text: $email)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.emailAddress)
                    .frame(maxWidth: 300)

                SecureField("Password", text: $password)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(isSignUp ? .newPassword : .password)
                    .frame(maxWidth: 300)
            }

            // Error
            if let error = authController.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 300)
            }

            // Buttons
            VStack(spacing: 8) {
                Button(action: submit) {
                    if authController.isLoading {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text(isSignUp ? "Sign Up" : "Sign In")
                            .frame(maxWidth: 300)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(email.isEmpty || password.isEmpty || authController.isLoading)

                Button(isSignUp ? "Already have an account? Sign In" : "Don't have an account? Sign Up") {
                    isSignUp.toggle()
                    authController.errorMessage = nil
                }
                .buttonStyle(.plain)
                .font(.caption)
                .foregroundStyle(.blue)
            }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onSubmit(submit)
    }

    private func submit() {
        guard !email.isEmpty, !password.isEmpty else { return }
        if isSignUp && password.count < 8 {
            authController.errorMessage = "Password must be at least 8 characters."
            return
        }
        Task {
            if isSignUp {
                await authController.signUp(email: email, password: password)
            } else {
                await authController.signIn(email: email, password: password)
            }
        }
    }
}
