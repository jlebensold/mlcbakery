from fastapi.testclient import TestClient
# sqlalchemy sync imports, engine, sessionmaker, override_get_db, and fixture are now handled by conftest.py
# Keep necessary imports:
from datetime import datetime
import pytest
import base64
import asyncio # Needed for pytest.mark.asyncio
import httpx
import python_multipart

from mlcbakery.main import app # Keep app import if needed for client
# Model imports might still be needed if tests reference them directly
from mlcbakery.models import Base, Dataset, Collection, Activity, Entity

# Tests start here, marked as async and using local async client
@pytest.mark.asyncio
async def test_create_dataset():
    """Test creating a new dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create prerequisite collection for isolation
        collection_data = {"name": "Create DS Collection Async", "description": "For create_dataset test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_id_to_use = coll_resp.json()["id"]

        dataset_data = {
            "name": "New Dataset Async",
            "data_path": "/path/to/data3/async",
            "format": "json",
            "collection_id": collection_id_to_use,
            "entity_type": "dataset",
            "metadata_version": "1.0",
            "dataset_metadata": {
                "description": "New async test dataset",
                "tags": ["new", "async"],
            },
        }
        response = await ac.post("/api/v1/datasets/", json=dataset_data)
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == dataset_data["name"]
        assert data["data_path"] == dataset_data["data_path"]
        assert data["format"] == dataset_data["format"]
        assert data["collection_id"] == dataset_data["collection_id"]
        assert data["entity_type"] == dataset_data["entity_type"]
        assert data["metadata_version"] == dataset_data["metadata_version"]
        assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_list_datasets():
    """Test getting all datasets."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a known collection first
        collection_data = {"name": "List DS Collection", "description": "For list ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]

        # Create some known datasets first to ensure test isolation
        datasets_to_create = [
            {"name": "List Dataset 1", "data_path": "/list/1", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use},
            {"name": "List Dataset 2", "data_path": "/list/2", "format": "parquet", "entity_type": "dataset", "collection_id": collection_id_to_use}
        ]
        created_ids = []
        for ds_data in datasets_to_create:
            resp = await ac.post("/api/v1/datasets/", json=ds_data)
            assert resp.status_code == 200
            created_ids.append(resp.json()["id"])

        response = await ac.get("/api/v1/datasets/")
        assert response.status_code == 200
        data = response.json()
        # Check that *at least* the datasets we created are present
        fetched_ids = {item["id"] for item in data}
        assert set(created_ids).issubset(fetched_ids)

        # Optional: Verify specific data points if needed, comparing against datasets_to_create

@pytest.mark.asyncio
async def test_list_datasets_pagination():
    """Test pagination of datasets."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a known collection first
        collection_data = {"name": "Paginate DS Collection Async", "description": "For paginate_datasets test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]

        # Create known datasets for pagination test
        base_name = "PaginateDSAsync"
        datasets_to_create = [
            {"name": f"{base_name}_{i}", "data_path": f"/paginate/a{i}", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
            for i in range(5) # Create 5 datasets
        ]
        # start by deleting any existing datasets with this base name
        response = await ac.get(f"/api/v1/datasets/?name={base_name}")
        assert response.status_code == 200
        existing_datasets = response.json()
        for ds in existing_datasets:
            delete_resp = await ac.delete(f"/api/v1/datasets/{ds['id']}")
            assert delete_resp.status_code == 200
        
        created_ids = []
        for ds_data in datasets_to_create:
            resp = await ac.post("/api/v1/datasets/", json=ds_data)
            assert resp.status_code == 200, f"Failed creating {ds_data['name']}: {resp.text}"
            created_ids.append(resp.json()["id"])
    
        # Fetch with skip and limit
        response = await ac.get("/api/v1/datasets/?skip=2&limit=2")
        assert response.status_code == 200
        paginated_data = response.json()
        assert len(paginated_data) == 2
        
        # Verify the *IDs* returned match the expected slice of IDs created *in this test*
        sorted_created_ids = sorted(created_ids)
        if len(sorted_created_ids) >= 4:
            expected_ids = sorted_created_ids[2:4] # 3rd and 4th created IDs
            fetched_ids = [d["id"] for d in paginated_data]
            assert fetched_ids == expected_ids, f"Expected IDs {expected_ids} but got {fetched_ids}"
        else:
            pytest.fail("Less than 4 datasets created for pagination check")

        # Optional: Verify names if IDs match (more robust check)
        # fetched_names = [d["name"] for d in paginated_data]
        # expected_names = [f"{base_name}_{i}" for i in [2, 3]] # Assuming IDs correspond to indices 2, 3
        # assert fetched_names == expected_names

@pytest.mark.asyncio
async def test_get_dataset():
    """Test getting a specific dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Get DS Collection", "description": "For get ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        # Create a dataset to get
        ds_data = {"name": "GetMeDS", "data_path": "/get/me", "format": "json", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        # Then get the specific dataset
        response = await ac.get(f"/api/v1/datasets/{dataset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == ds_data["name"]
        assert data["data_path"] == ds_data["data_path"]
        assert data["format"] == ds_data["format"]
        assert data["collection_id"] == ds_data["collection_id"]
        assert data["entity_type"] == ds_data["entity_type"]

@pytest.mark.asyncio
async def test_get_nonexistent_dataset():
    """Test getting a dataset that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/datasets/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_update_dataset():
    """Test updating a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Update DS Collection", "description": "For update ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        # Create a dataset to update
        ds_data = {"name": "UpdateMeDS", "data_path": "/update/me", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        # Update the dataset
        update_data = {
            "name": "Updated Dataset Async",
            "data_path": "/path/to/updated/data_async",
            "format": "json",
            "collection_id": collection_id_to_use, # Keep same collection or change if needed
            "entity_type": "dataset", # Should remain dataset
            "metadata_version": "2.0",
            "dataset_metadata": {
                "description": "Updated async test dataset",
                "tags": ["updated", "async"],
            },
        }
        response = await ac.put(f"/api/v1/datasets/{dataset_id}", json=update_data)
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == update_data["name"]
        assert data["data_path"] == update_data["data_path"]
        assert data["format"] == update_data["format"]
        assert data["collection_id"] == update_data["collection_id"]
        assert data["metadata_version"] == update_data["metadata_version"]
        assert data["dataset_metadata"] == update_data["dataset_metadata"]

@pytest.mark.asyncio
async def test_update_nonexistent_dataset():
    """Test updating a dataset that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        update_data = {
            "name": "Updated Dataset Fail",
            "data_path": "/update/fail",
            "format": "csv",
            "entity_type": "dataset",
        }
        response = await ac.put("/api/v1/datasets/99999", json=update_data)

        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_delete_dataset():
    """Test deleting a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Delete DS Collection", "description": "For delete ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        # Create a dataset to delete
        ds_data = {"name": "DeleteMeDS", "data_path": "/delete/me", "format": "txt", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        # Delete the dataset
        delete_response = await ac.delete(f"/api/v1/datasets/{dataset_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Dataset deleted successfully"

        # Verify it's deleted
        get_response = await ac.get(f"/api/v1/datasets/{dataset_id}")
        assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_nonexistent_dataset():
    """Test deleting a dataset that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/datasets/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_update_dataset_metadata():
    """Test updating only the metadata of a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Meta Update DS Collection", "description": "For meta update ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        # Create a dataset
        ds_data = {"name": "MetadataUpdateDS", "data_path": "/metadata/update", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        # Update only metadata
        metadata_update = {
            "metadata_version": "1.1",
            "dataset_metadata": {"author": "Test Author", "license": "MIT"}
        }
        response = await ac.patch(f"/api/v1/datasets/{dataset_id}/metadata", json=metadata_update)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == ds_data["name"] # Name should be unchanged
        assert data["dataset_metadata"]["dataset_metadata"] == metadata_update["dataset_metadata"]

@pytest.mark.asyncio
async def test_update_metadata_nonexistent_dataset():
    """Test updating metadata of a nonexistent dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        metadata_update = {
            "metadata_version": "1.1",
            "dataset_metadata": {"author": "Test Author"}
        }
        response = await ac.patch("/api/v1/datasets/99999/metadata", json=metadata_update)
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_invalid_pagination():
    """Test invalid pagination parameters (negative skip/limit)."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response_skip = await ac.get("/api/v1/datasets/?skip=-1&limit=10")
        assert response_skip.status_code == 400 # FastAPI validation error

        response_limit = await ac.get("/api/v1/datasets/?skip=0&limit=-1")
        assert response_limit.status_code == 400 # FastAPI validation error

@pytest.mark.asyncio
async def test_update_dataset_preview():
    """Test updating the preview of a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection and dataset first
        collection_data = {"name": "Preview Update DS Collection Async", "description": "For update_preview test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        ds_data = {"name": "PreviewUpdateDSAsync", "data_path": "/preview/updatea", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        # 1. Prepare file details
        preview_content = b"Sample preview content async"
        preview_type = "text/plain"
        file_name = "preview.txt" # Can be anything reasonable
        preview_update_body = base64.b64encode(preview_content).decode('utf-8')
        # 2. Create the 'files' dictionary
        #    The key 'preview_update' MUST match the endpoint parameter name
        files_data = {
            "preview_update": (file_name, preview_update_body, preview_type)
        }

        # 3. Make the PUT request using the 'files' parameter
        response = await ac.put(f"/api/v1/datasets/{dataset_id}/preview", files=files_data)

        # 4. Assertions...
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["preview_type"] == preview_type
        assert data["id"] == dataset_id
        assert data["name"] == ds_data["name"]

@pytest.mark.asyncio
async def test_update_nonexistent_dataset_preview():
    """Test updating preview of a nonexistent dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        preview_content = b"Sample preview content"
        preview_base64 = base64.b64encode(preview_content).decode('utf-8')
        preview_type = "text/plain"
        preview_data = {
            "preview": preview_base64,
            "preview_type": preview_type
        }
        response = await ac.patch("/api/v1/datasets/99999/preview", json=preview_data)
        assert response.status_code == 405

@pytest.mark.asyncio
async def test_get_nonexistent_dataset_preview():
    """Test getting preview of a nonexistent dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/datasets/99999/preview")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_missing_preview():
    """Test getting preview for a dataset that has none."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Missing Preview DS Collection", "description": "For missing preview ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]
        # Create a dataset without a preview
        ds_data = {"name": "NoPreviewDS", "data_path": "/no/preview", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        create_resp = await ac.post("/api/v1/datasets/", json=ds_data)
        assert create_resp.status_code == 200
        dataset_id = create_resp.json()["id"]

        response = await ac.get(f"/api/v1/datasets/{dataset_id}/preview")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_dataset_upstream_tree():
    """Test retrieving the upstream provenance tree for a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create a collection
        collection_data = {"name": "Upstream Tree DS Collection", "description": "For upstream tree ds test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200
        collection_id_to_use = coll_resp.json()["id"]

        # 1. Create initial datasets (DS1, DS2)
        ds1_data = {"name": "UpstreamDS1", "data_path": "/up/1", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        ds2_data = {"name": "UpstreamDS2", "data_path": "/up/2", "format": "csv", "entity_type": "dataset", "collection_id": collection_id_to_use}
        ds1_resp = await ac.post("/api/v1/datasets/", json=ds1_data)
        ds2_resp = await ac.post("/api/v1/datasets/", json=ds2_data)
        assert ds1_resp.status_code == 200
        assert ds2_resp.status_code == 200
        ds1_id = ds1_resp.json()["id"]
        ds2_id = ds2_resp.json()["id"]

        # 2. Create an activity that uses DS1 and DS2 to produce DS3
        ds3_data = {"name": "UpstreamDS3", "data_path": "/up/3", "format": "parquet", "entity_type": "dataset", "collection_id": collection_id_to_use}
        ds3_resp = await ac.post("/api/v1/datasets/", json=ds3_data)
        assert ds3_resp.status_code == 200
        ds3_id = ds3_resp.json()["id"]
        act1_data = {"name": "Activity 1", "input_entity_ids": [ds1_id, ds2_id], "output_entity_id": ds3_id}
        act1_resp = await ac.post("/api/v1/activities/", json=act1_data)
        assert act1_resp.status_code == 200
        act1_id = act1_resp.json()["id"]

        # 3. Create an activity that uses DS3 to produce DS4
        ds4_data = {"name": "UpstreamDS4", "data_path": "/up/4", "format": "json", "entity_type": "dataset", "collection_id": collection_id_to_use}
        ds4_resp = await ac.post("/api/v1/datasets/", json=ds4_data)
        assert ds4_resp.status_code == 200
        ds4_id = ds4_resp.json()["id"]
        act2_data = {"name": "Activity 2", "input_entity_ids": [ds3_id], "output_entity_id": ds4_id}
        act2_resp = await ac.post("/api/v1/activities/", json=act2_data)
        assert act2_resp.status_code == 200
        act2_id = act2_resp.json()["id"]

        # 4. Get the upstream tree for DS4
        response = await ac.get(f"/api/v1/datasets/{ds4_id}/upstream")
        assert response.status_code == 200
        tree = response.json()

        # 5. Verify the tree structure (basic checks)
        assert tree["id"] == ds4_id
        assert tree["name"] == "UpstreamDS4"
        assert tree["generated_by_activity"] is not None
        assert tree["generated_by_activity"]["id"] == act2_id
        assert tree["generated_by_activity"]["name"] == "Activity 2"

        assert len(tree["generated_by_activity"]["used_inputs"]) == 1
        input1 = tree["generated_by_activity"]["used_inputs"][0]
        assert input1["id"] == ds3_id
        assert input1["name"] == "UpstreamDS3"
        assert input1["generated_by_activity"] is not None
        assert input1["generated_by_activity"]["id"] == act1_id
        assert input1["generated_by_activity"]["name"] == "Activity 1"

        assert len(input1["generated_by_activity"]["used_inputs"]) == 2
        input1_1 = input1["generated_by_activity"]["used_inputs"][0] # Order might vary
        input1_2 = input1["generated_by_activity"]["used_inputs"][1]
        input_ids = {input1_1["id"], input1_2["id"]}
        assert input_ids == {ds1_id, ds2_id}

        # Check one of the base datasets
        base_ds = input1_1 if input1_1["id"] == ds1_id else input1_2
        assert base_ds["name"] == "UpstreamDS1"
        assert base_ds["generated_by_activity"] is None # Base dataset

@pytest.mark.asyncio
async def test_get_nonexistent_dataset_upstream_tree():
    """Test getting upstream tree for a nonexistent dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/datasets/99999/upstream")
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"
