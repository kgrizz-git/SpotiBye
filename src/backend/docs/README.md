# SpotiBye API Documentation

This directory contains comprehensive API documentation for the SpotiBye Cloudflare Workers backend.

## Files Overview

### `openapi.yaml`
Complete OpenAPI 3.0.3 specification for the SpotiBye API, including:
- All API endpoints with detailed descriptions
- Request/response schemas
- Authentication methods
- Error handling
- Examples for each endpoint

### `swagger-ui.html`
Interactive Swagger UI interface for exploring and testing the API. Features:
- Visual API exploration
- Interactive testing of endpoints
- Request/response examples
- Schema documentation
- Authentication support

### `README.md`
This file - documentation overview and usage instructions.

## Using the Documentation

### Local Development
1. Start the local development server:
   ```bash
   cd src/backend
   npm run dev
   ```

2. Open the Swagger UI in your browser:
   ```
   http://localhost:8787/docs/swagger-ui.html
   ```

3. Alternatively, view the raw OpenAPI spec:
   ```
   http://localhost:8787/docs/openapi.yaml
   ```

### Production
Access the documentation at:
```
https://spotibye-api.workers.dev/docs/swagger-ui.html
```

## API Overview

### Base URLs
- **Production**: `https://spotibye-api.workers.dev`
- **Development**: `https://spotibye-api-dev.workers.dev`
- **Local**: `http://localhost:8787`

### Authentication
The API uses JWT tokens for authentication. Follow this flow:

1. **Initiate OAuth**: `POST /auth/spotify/login`
2. **Handle Callback**: `GET /auth/spotify/callback`
3. **Use Token**: Include JWT in Authorization header: `Bearer <token>`

### Main Endpoints

#### System
- `GET /health` - Health check

#### Authentication
- `POST /auth/spotify/login` - Initiate Spotify OAuth
- `GET /auth/spotify/callback` - Handle OAuth callback

#### Spotify Data
- `GET /spotify/playlists` - Get user playlists
- `GET /spotify/playlists/{id}` - Get playlist details
- `GET /spotify/playlists/{id}/items` - Get playlist items
- `GET /spotify/playlists/{id}/tracks` - Backward-compatible alias for playlist items

#### Analysis
- `POST /analysis/playlist/{id}` - Analyze playlist

#### Export
- `POST /export/playlist/{id}` - Generate export
- `GET /export/playlist/{id}/download` - Download export

## Testing with Swagger UI

1. **Authentication Flow**:
   - Use the "Authorize" button to add your JWT token
   - For testing, you can first call `/auth/spotify/login` to get a token

2. **Interactive Testing**:
   - Click "Try it out" on any endpoint
   - Fill in required parameters
   - Click "Execute" to test the endpoint
   - View the response and status code

3. **Schema Exploration**:
   - Click on any schema name to see detailed structure
   - View examples for request/response formats
   - Check required fields and data types

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "additional": "context"
    }
  }
}
```

Common error codes:
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error

## Rate Limiting

The API implements rate limiting to ensure fair usage:
- Standard endpoints: 100 requests per minute
- Export endpoints: 10 requests per minute
- Analysis endpoints: 20 requests per minute

## Data Formats

### Request Formats
- JSON for most endpoints
- Form data for OAuth callback
- Binary for file uploads (if applicable)

### Response Formats
- JSON for API responses
- Binary for file downloads
- CSV/JSON/XLSX for exports

## Performance Considerations

- **Pagination**: Use `limit` and `offset` parameters for large datasets
- **Caching**: Responses are cached where appropriate
- **Timeouts**: Requests timeout after 30 seconds
- **Size Limits**: Maximum request size is 10MB

## Development

### Updating Documentation
1. Edit `openapi.yaml` with your changes
2. Test changes with Swagger UI
3. Update any related code examples
4. Commit changes with documentation updates

### Validation
Use OpenAPI validator tools to ensure spec validity:
```bash
npx @apidevtools/swagger-parser validate docs/openapi.yaml
```

### Code Generation
Generate client SDKs from the OpenAPI spec:
```bash
npx openapi-generator-cli generate -i docs/openapi.yaml -g typescript-axios -o ./generated-client
```

## Support

For API documentation issues:
- Check the OpenAPI specification for endpoint details
- Test with Swagger UI for interactive debugging
- Review error messages for specific issues
- Contact the development team for additional support

## Version History

- **v1.0.0** - Initial API specification with all core endpoints
  - Authentication flow
  - Spotify data retrieval
  - Playlist analysis
  - Export functionality
