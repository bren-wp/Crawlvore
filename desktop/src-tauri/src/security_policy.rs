//! Validates loopback handshakes and external navigation targets.
use std::io;
use tauri::Url;

pub(crate) fn invalid(message: &str) -> io::Error { io::Error::other(message) }

pub(crate) fn ready_url(line: &str) -> Result<Url, io::Error> {
    let raw = line.trim().strip_prefix("CRAWLVORA_READY ").ok_or_else(|| invalid("Invalid worker handshake"))?;
    let url = Url::parse(raw).map_err(|_| invalid("Invalid worker address"))?;
    let secret = url.path().strip_prefix("/session/").unwrap_or("");
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1") || url.port().is_none()
        || !url.username().is_empty() || url.password().is_some()
        || url.query().is_some() || url.fragment().is_some()
        || secret.len() != 64 || !secret.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(invalid("Rejected worker address"));
    }
    Ok(url)
}

// Only ordinary public-domain HTTP(S) links may leave the local webview.
// Do not allow file URLs, custom protocols, IP literals, local hostnames or embedded credentials.
pub(crate) fn allowed_external_url(url: &Url) -> bool {
    if !matches!(url.scheme(), "http" | "https") || !url.username().is_empty() || url.password().is_some() {
        return false;
    }
    let Some(host) = url.host_str() else { return false; };
    let host = host.trim_end_matches('.').to_ascii_lowercase();
    if host.parse::<std::net::IpAddr>().is_ok() || !host.contains('.') || host.contains(':') {
        return false;
    }
    !["localhost", "local", "internal", "test", "invalid", "onion"].iter()
        .any(|suffix| host == *suffix || host.ends_with(&format!(".{suffix}")))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn external_links_are_restricted_to_web_domains() {
        for value in ["https://example.com/path?q=1", "http://www.example.org/"] {
            assert!(allowed_external_url(&Url::parse(value).unwrap()));
        }
        for value in ["file:///etc/passwd", "javascript:alert(1)", "mailto:test@example.com",
            "https://user:pass@example.com", "http://localhost", "http://127.0.0.1",
            "http://192.168.1.1", "http://[::1]", "https://service.internal/",
            "https://foo.localhost/", "https://foo.local/"] {
            assert!(!allowed_external_url(&Url::parse(value).unwrap()), "{value}");
        }
    }

    #[test]
    fn only_accepts_loopback_session() {
        let token = "a".repeat(64);
        assert!(ready_url(&format!("CRAWLVORA_READY http://127.0.0.1:49152/session/{token}")).is_ok());
        for host in ["https://127.0.0.1:49152", "http://localhost:49152", "http://example.com:49152", "http://127.0.0.1"] {
            assert!(ready_url(&format!("CRAWLVORA_READY {host}/session/{token}")).is_err());
        }
        assert!(ready_url("CRAWLVORA_READY http://127.0.0.1:49152/session/bad").is_err());
    }
}
