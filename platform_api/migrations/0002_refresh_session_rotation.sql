CREATE OR REPLACE FUNCTION carpan.consume_refresh_token(p_token_hash CHAR(64))
RETURNS TABLE (company_id UUID, user_id UUID, display_name VARCHAR(160), role VARCHAR(30))
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, carpan
AS $$
DECLARE token_row RECORD;
BEGIN
    SELECT t.id, t.company_id, t.user_id, u.display_name, m.role
    INTO token_row
    FROM carpan.refresh_tokens t
    JOIN carpan.users u ON u.id = t.user_id
    JOIN carpan.company_memberships m ON m.company_id = t.company_id AND m.user_id = t.user_id
    JOIN carpan.companies c ON c.id = t.company_id
    LEFT JOIN carpan.device_registrations d ON d.id = t.device_registration_id
    WHERE t.token_hash = p_token_hash AND t.revoked_at IS NULL AND t.expires_at > now()
      AND u.status = 'ACTIVE' AND m.active AND c.status = 'ACTIVE'
      AND (d.id IS NULL OR d.status = 'ACTIVE')
    FOR UPDATE OF t;
    IF NOT FOUND THEN RETURN; END IF;
    UPDATE carpan.refresh_tokens SET revoked_at = now() WHERE id = token_row.id;
    RETURN QUERY SELECT token_row.company_id, token_row.user_id, token_row.display_name, token_row.role;
END;
$$;
