import CommonCrypto
import CryptoKit
import Foundation

final class Delegate: NSObject, URLSessionDelegate {
  // ruleid: swift-trust-every-server-certificate
  func acceptsAll(
    _ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
  ) {
    completionHandler(
      .useCredential, URLCredential(trust: challenge.protectionSpace.serverTrust!))
  }

  func pinned(
    _ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
  ) {
    guard let trust = challenge.protectionSpace.serverTrust,
      SecTrustEvaluateWithError(trust, nil)
    else { return }
    completionHandler(.useCredential, URLCredential(trust: trust))
  }
}

func digests(_ data: Data) {
  var out = [UInt8](repeating: 0, count: 16)
  // ruleid: swift-weak-hash
  _ = Insecure.SHA1.hash(data: data)
  // ruleid: swift-weak-hash
  _ = CC_MD5([UInt8](data), CC_LONG(data.count), &out)
  _ = SHA256.hash(data: data)
}

// ruleid: swift-weak-cipher
let legacy = kCCAlgorithm3DES
let modern = kCCAlgorithmAES

// ruleid: swift-hardcoded-secret
let serviceApiKey = "xxxxxxxxxxxxxxxxxxxxxxxx"
let tokenKey = "auth_token"
let apiKeyHeader = "X-Api-Key"

func store() {
  // ruleid: swift-secret-in-user-defaults
  UserDefaults.standard.set("value", forKey: "authToken")
  UserDefaults.standard.set("dark", forKey: "theme")
  // ruleid: swift-keychain-always-accessible
  _ = kSecAttrAccessibleAlways
  _ = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
}
