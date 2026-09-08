-- Users are global identities, but the application role must only see users
-- belonging to the currently selected company. Bootstrap uses the schema owner.
ALTER TABLE carpan.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_tenant_scope ON carpan.users
    USING (
        EXISTS (
            SELECT 1 FROM carpan.company_memberships m
            WHERE m.user_id = users.id
              AND m.company_id = NULLIF(current_setting('app.company_id', true), '')::uuid
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM carpan.company_memberships m
            WHERE m.user_id = users.id
              AND m.company_id = NULLIF(current_setting('app.company_id', true), '')::uuid
        )
    );
