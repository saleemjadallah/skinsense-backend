import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.services.orbo_service import OrboSkinAnalysisService
from app.middleware.orbo_middleware import OrboAnalysisMiddleware
import aiohttp

@pytest.fixture
def orbo_service():
    """Create ORBO service instance for testing"""
    return OrboSkinAnalysisService()

@pytest.fixture
def mock_db():
    """Create mock database for testing"""
    mock_db = Mock()
    mock_db.skin_analyses = Mock()
    mock_db.skin_analyses.insert_one = AsyncMock()
    mock_db.skin_analyses.update_one = AsyncMock()
    mock_db.skin_analyses.find_one = AsyncMock()
    return mock_db

@pytest.fixture
def orbo_service_with_middleware(mock_db):
    """Create ORBO service with middleware for testing"""
    return OrboSkinAnalysisService(mock_db)

@pytest.fixture
def sample_image_data():
    """Sample image data for testing"""
    return b"fake_image_data_bytes"

@pytest.fixture
def sample_orbo_response():
    """Sample ORBO API response"""
    return {
        "success": True,
        "statusCode": 200,
        "message": "Skin analysis completed successfully",
        "data": {
            "output_score": [
                {"concern": "skin_health", "score": 76, "riskLevel": 2},
                {"concern": "hydration", "score": 85, "riskLevel": 1},
                {"concern": "smoothness", "score": 90, "riskLevel": 1},
                {"concern": "skin_dullness", "score": 20, "riskLevel": 1},
                {"concern": "dark_spots", "score": 15, "riskLevel": 1},
                {"concern": "firmness", "score": 88, "riskLevel": 1},
                {"concern": "face_wrinkles", "score": 10, "riskLevel": 1},
                {"concern": "acne", "score": 5, "riskLevel": 1},
                {"concern": "dark_circle", "score": 25, "riskLevel": 1},
                {"concern": "redness", "score": 12, "riskLevel": 1}
            ],
            "input_image": "https://example.com/input.jpg",
            "annotations": {
                "acne": "https://example.com/acne.jpg",
                "dark_circle": "https://example.com/dark_circle.jpg"
            }
        }
    }

class TestOrboService:
    """Test ORBO service basic functionality"""
    
    @pytest.mark.asyncio
    async def test_get_presigned_url_success(self, orbo_service):
        """Test successful presigned URL retrieval"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "data": {
                    "uploadSignedUrl": "https://s3.example.com/presigned-url",
                    "session_id": "test-session-id"
                }
            })
            
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await orbo_service.get_presigned_url()
            
            assert result['success'] is True
            assert result['upload_url'] == "https://s3.example.com/presigned-url"
            assert result['session_id'] == "test-session-id"
    
    @pytest.mark.asyncio
    async def test_upload_image_to_s3_success(self, orbo_service, sample_image_data):
        """Test successful image upload to S3"""
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            
            mock_session.return_value.__aenter__.return_value.put.return_value.__aenter__.return_value = mock_response
            
            result = await orbo_service.upload_image_to_s3(
                "https://s3.example.com/presigned-url",
                sample_image_data
            )
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_process_analysis_response(self, orbo_service, sample_orbo_response):
        """Test processing of ORBO response"""
        result = orbo_service._process_analysis_response(sample_orbo_response)
        
        assert result['success'] is True
        assert result['metrics']['overall_skin_health_score'] == 76
        assert result['metrics']['hydration'] == 85
        assert result['metrics']['smoothness'] == 90
        assert result['metrics']['radiance'] == 80  # 100 - 20 (skin_dullness)
        assert result['metrics']['dark_spots'] == 85  # 100 - 15
        assert result['metrics']['firmness'] == 88
        assert result['metrics']['fine_lines_wrinkles'] == 90  # 100 - 10
        assert result['metrics']['acne'] == 95  # 100 - 5
        assert result['metrics']['dark_circles'] == 75  # 100 - 25
        assert result['metrics']['redness'] == 88  # 100 - 12
    
    @pytest.mark.asyncio
    async def test_complete_analysis_pipeline(self, orbo_service, sample_image_data):
        """Test complete analysis pipeline"""
        with patch.object(orbo_service, 'get_presigned_url') as mock_presigned:
            mock_presigned.return_value = {
                'success': True,
                'upload_url': 'https://s3.example.com/presigned',
                'session_id': 'test-session'
            }
            
            with patch.object(orbo_service, 'upload_image_to_s3') as mock_upload:
                mock_upload.return_value = True
                
                with patch.object(orbo_service, 'get_skin_analysis') as mock_analysis:
                    mock_analysis.return_value = {
                        'success': True,
                        'metrics': {'overall_skin_health_score': 75}
                    }
                    
                    result = await orbo_service.complete_analysis_pipeline(sample_image_data)
                    
                    assert result['success'] is True
                    assert result['session_id'] == 'test-session'
                    assert result['metrics']['overall_skin_health_score'] == 75

class TestOrboMiddleware:
    """Test ORBO middleware functionality"""
    
    @pytest.mark.asyncio
    async def test_pre_analysis_middleware(self, mock_db, sample_image_data):
        """Test pre-analysis middleware"""
        middleware = OrboAnalysisMiddleware(mock_db)
        
        with patch.object(middleware, '_store_image_internally') as mock_store:
            mock_store.return_value = "https://our-s3.example.com/image.jpg"
            
            result = await middleware.pre_analysis_middleware(
                user_id="test-user-id",
                image_data=sample_image_data,
                image_metadata={"filename": "test.jpg"}
            )
            
            assert result['success'] is True
            assert 'internal_analysis_id' in result
            assert result['internal_image_url'] == "https://our-s3.example.com/image.jpg"
            assert result['database_record_created'] is True
            
            # Verify database insert was called
            mock_db.skin_analyses.insert_one.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_analysis_middleware(self, mock_db):
        """Test post-analysis middleware"""
        middleware = OrboAnalysisMiddleware(mock_db)
        
        orbo_response = {
            'success': True,
            'metrics': {'overall_skin_health_score': 80},
            'annotations': {'acne': 'url'}
        }
        
        result = await middleware.post_analysis_middleware(
            internal_analysis_id="test-analysis-id",
            orbo_response=orbo_response,
            orbo_session_id="orbo-session-id"
        )
        
        assert result['success'] is True
        assert result['analysis_complete'] is True
        assert result['database_updated'] is True
        
        # Verify database update was called
        mock_db.skin_analyses.update_one.assert_called_once()

class TestOrboIntegration:
    """Test ORBO service with middleware integration"""
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_with_middleware(self, orbo_service_with_middleware, sample_image_data):
        """Test complete pipeline with data sovereignty"""
        # Mock the middleware methods
        with patch.object(orbo_service_with_middleware.middleware, 'pre_analysis_middleware') as mock_pre:
            mock_pre.return_value = {
                'success': True,
                'internal_analysis_id': 'internal-id',
                'database_record_created': True
            }
            
            # Mock the ORBO API calls
            with patch.object(orbo_service_with_middleware, 'get_presigned_url') as mock_presigned:
                mock_presigned.return_value = {
                    'success': True,
                    'upload_url': 'https://s3.example.com/presigned',
                    'session_id': 'orbo-session'
                }
                
                with patch.object(orbo_service_with_middleware, 'upload_image_to_s3') as mock_upload:
                    mock_upload.return_value = True
                    
                    with patch.object(orbo_service_with_middleware, 'get_skin_analysis') as mock_analysis:
                        mock_analysis.return_value = {
                            'success': True,
                            'metrics': {'overall_skin_health_score': 85}
                        }
                        
                        with patch.object(orbo_service_with_middleware.middleware, 'post_analysis_middleware') as mock_post:
                            mock_post.return_value = {
                                'success': True,
                                'database_updated': True
                            }
                            
                            result = await orbo_service_with_middleware.complete_analysis_pipeline_with_middleware(
                                image_data=sample_image_data,
                                user_id="test-user",
                                image_metadata={"test": "metadata"}
                            )
                            
                            assert result['success'] is True
                            assert result['internal_analysis_id'] == 'internal-id'
                            assert result['data_sovereignty_compliant'] is True
                            assert result['database_stored'] is True
                            assert result['database_updated'] is True

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])