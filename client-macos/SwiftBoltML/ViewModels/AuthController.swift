import Foundation
import Supabase
import Auth
import os.log

// MARK: - Auth Controller

/// Manages Supabase authentication state using `@Observable` for fine-grained
/// SwiftUI observation. Listens to `authStateChanges` async stream for sign-in,
/// sign-out, and token refresh events.
@Observable
@MainActor
final class AuthController {

    // MARK: - Published State

    var isAuthenticated = false
    var currentUser: User?
    var errorMessage: String?
    var isLoading = false

    // MARK: - Private

    private var authTask: Task<Void, Never>?
    private static let logger = Logger(subsystem: "com.swiftboltml", category: "AuthController")

    // MARK: - Lifecycle

    /// Start listening for auth state changes. Call once from the app entry point's `.task` modifier.
    func startListening() {
        guard authTask == nil else { return }
        authTask = Task { [weak self] in
            guard let self else { return }
            for await (event, session) in SupabaseService.shared.client.auth.authStateChanges {
                guard !Task.isCancelled else { return }
                switch event {
                case .signedIn, .tokenRefreshed:
                    self.isAuthenticated = true
                    self.currentUser = session?.user
                    Self.logger.info("Auth event: \(String(describing: event))")
                case .signedOut:
                    self.isAuthenticated = false
                    self.currentUser = nil
                    Self.logger.info("User signed out")
                default:
                    break
                }
            }
        }
    }

    deinit {
        authTask?.cancel()
        authTask = nil
    }

    // MARK: - Actions

    func signIn(email: String, password: String) async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        do {
            let session = try await SupabaseService.shared.client.auth.signIn(
                email: email,
                password: password
            )
            isAuthenticated = true
            currentUser = session.user
            Self.logger.info("Signed in: \(session.user.id)")
        } catch {
            Self.logger.error("Sign in failed: \(error)")
            errorMessage = "Unable to sign in. Please check your credentials and try again."
        }
        isLoading = false
    }

    func signUp(email: String, password: String) async {
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        do {
            let response = try await SupabaseService.shared.client.auth.signUp(
                email: email,
                password: password
            )
            if response.session != nil {
                // Auto-confirmed — already signed in
                isAuthenticated = true
                currentUser = response.user
                Self.logger.info("Signed up and signed in")
            } else {
                errorMessage = "Check your email for a confirmation link."
                Self.logger.info("Confirmation email sent")
            }
        } catch {
            Self.logger.error("Sign up failed: \(error)")
            errorMessage = "Unable to create account. Please try again."
        }
        isLoading = false
    }

    func signOut() async {
        do {
            try await SupabaseService.shared.client.auth.signOut()
            isAuthenticated = false
            currentUser = nil
        } catch {
            Self.logger.error("Sign out failed: \(error)")
            errorMessage = "Unable to sign out. Please try again."
        }
    }
}
