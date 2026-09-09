CREATE TABLE IF NOT EXISTS carpan.user_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES carpan.companies(id),
    username VARCHAR(80) NOT NULL,
    display_name VARCHAR(160) NOT NULL,
    role VARCHAR(30) NOT NULL,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_by_user_id UUID NOT NULL REFERENCES carpan.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_invitations_role_valid CHECK (role IN ('ADMIN', 'OPERATOR', 'APPROVER', 'AUDITOR'))
);

CREATE INDEX IF NOT EXISTS idx_user_invitations_company_pending
    ON carpan.user_invitations(company_id, username, expires_at DESC)
    WHERE accepted_at IS NULL AND revoked_at IS NULL;

ALTER TABLE carpan.user_invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY invitations_tenant_scope ON carpan.user_invitations
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::uuid);

CREATE OR REPLACE FUNCTION carpan.accept_user_invitation(
    p_token_hash CHAR(64),
    p_password_hash TEXT
)
RETURNS TABLE (company_code VARCHAR, username VARCHAR, display_name VARCHAR, role VARCHAR)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, carpan
AS $$
DECLARE invitation_row carpan.user_invitations%ROWTYPE;
DECLARE created_user_id UUID;
BEGIN
    SELECT * INTO invitation_row
    FROM carpan.user_invitations
    WHERE token_hash = p_token_hash
      AND accepted_at IS NULL
      AND revoked_at IS NULL
      AND expires_at > now()
    FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;

    INSERT INTO carpan.users(username, display_name, password_hash)
    VALUES (invitation_row.username, invitation_row.display_name, p_password_hash)
    RETURNING id INTO created_user_id;
    INSERT INTO carpan.company_memberships(company_id, user_id, role)
    VALUES (invitation_row.company_id, created_user_id, invitation_row.role);
    UPDATE carpan.user_invitations SET accepted_at = now() WHERE id = invitation_row.id;
    RETURN QUERY SELECT c.code, invitation_row.username, invitation_row.display_name, invitation_row.role
      FROM carpan.companies c WHERE c.id = invitation_row.company_id;
END;
$$;
REVOKE ALL ON FUNCTION carpan.accept_user_invitation(CHAR(64), TEXT) FROM PUBLIC;
