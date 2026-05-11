# Authentication and Access Control Flow

## Goal

Ensure MVP users operate inside their own workspace and cannot access unrelated fields, traps, uploads, predictions, or monitoring results.

## Authentication Method

The backend uses email/password login and signed JWT bearer access tokens.

Entry points:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

Tokens include:

- `sub`: authenticated user id
- `role`: user role
- `type`: `access`
- `iat`: issued-at timestamp
- `exp`: expiry timestamp

Invalid, expired, malformed, or wrong-type tokens return `401` with a generic credential message.

## Protected Backend Areas

These MVP workflows require an authenticated user:

- Field and trap management
- Map search used inside the protected field workflow
- Image upload and ingestion
- Upload/result retrieval
- Analytics, insights, monitoring, and environmental views
- Exploratory analysis/reporting
- Admin overview

## Workspace Ownership

Regular users are scoped to records linked to their user id or fields they own.

Data linkage:

- `FieldMap.owner_user_id` links fields to a workspace owner.
- `TrapPoint.field_id` links traps to a field/workspace.
- `TrapUpload.user_id` links uploads to the submitting user.
- `TrapUpload.field_id` and `trap_id` keep uploads traceable to field/trap context.
- `Detection.upload_id` links predictions to the stored upload.

Shared backend access logic uses `require_field_access` for field-scoped operations. Regular users must own the field. Admin users may inspect all workspaces.

## Role Behavior

Regular users can:

- Create and list their own fields.
- Add and rename traps in their own fields.
- Upload images to their own field or trap.
- Retrieve their own upload and prediction results.
- View analytics for their own workspace.

Admin users can:

- Review all fields/uploads/analytics.
- Access admin overview endpoints.

Admin-only endpoints use `require_admin` and return `403` for regular users.

## Error Handling

Expected access errors:

- `401`: missing, invalid, expired, malformed, or inactive-user token.
- `403`: authenticated user attempted to access another workspace or admin-only area.
- `404`: hidden result/field lookup where revealing existence is not appropriate, such as another user's upload result.

Authentication and permission errors intentionally avoid stack traces and sensitive backend details.

## Frontend Session Flow

The React frontend stores the bearer token in `localStorage` under `auth_token`.

Client flow:

1. Login or registration receives `access_token`.
2. The token is stored locally.
3. Protected routes call `/api/auth/me` to validate the session.
4. API client sends `Authorization: Bearer <token>` on protected requests.
5. Failed session refresh clears the local token and user state.
6. Protected UI routes redirect unauthenticated users to `/login`.

## MVP Testing Checklist

- Call protected endpoints without a token and verify `401`.
- Log in as user A and create a field/trap/upload.
- Log in as user B and verify user A's field/trap/upload/result cannot be accessed.
- Verify user B does not see user A data in analytics or environmental views.
- Verify admin can access overview and cross-workspace monitoring.
- Verify failed login/register attempts are throttled after repeated attempts.
- Verify frontend clears a stale token after `/api/auth/me` fails.
