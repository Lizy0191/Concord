//! Treat the child process endpoint announcement as untrusted input.
pub fn parse_announcement(line: &str) -> Option<String> {
    let endpoint = line.trim().strip_prefix("CCA_ENDPOINT=")?;
    if endpoint.contains('\r') || endpoint.contains('\n') { return None; }
    let url = reqwest::Url::parse(endpoint).ok()?;
    if url.scheme() != "http" || url.host_str() != Some("127.0.0.1")
        || url.port().is_none() || url.port() == Some(0)
        || !url.username().is_empty() || url.password().is_some()
        || url.query().is_some() || url.fragment().is_some() || url.path() != "/" {
        return None;
    }
    Some(url.origin().ascii_serialization())
}

#[cfg(test)]
mod tests {
    use super::parse_announcement;

    #[test]
    fn accepts_only_plain_ephemeral_loopback_origins() {
        assert_eq!(parse_announcement("CCA_ENDPOINT=http://127.0.0.1:38171\n"), Some("http://127.0.0.1:38171".into()));
        assert_eq!(parse_announcement("CCA_ENDPOINT=http://127.0.0.1:38171/"), Some("http://127.0.0.1:38171".into()));
    }

    #[test]
    fn rejects_credentials_paths_redirect_hosts_and_malformed_announcements() {
        for value in [
            "http://evil.invalid:38171", "https://127.0.0.1:38171", "http://127.0.0.1",
            "http://127.0.0.1:0", "http://user:secret@127.0.0.1:38171",
            "http://127.0.0.1:38171/private", "http://127.0.0.1:38171?token=secret",
            "http://127.0.0.1:38171#fragment", "http://127.0.0.1:38171\nCCA_ENDPOINT=http://evil.invalid",
        ] {
            assert_eq!(parse_announcement(&format!("CCA_ENDPOINT={value}")), None, "{value}");
        }
        assert_eq!(parse_announcement("ordinary process log"), None);
    }
}
