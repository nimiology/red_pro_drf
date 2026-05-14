from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import RedItem

class RedAPITests(APITestCase):
    def setUp(self):
        self.item = RedItem.objects.create(name="Test Item", description="Test Description")
        self.list_url = reverse('red-item-list')
        self.detail_url = reverse('red-item-detail', kwargs={'pk': self.item.pk})

    def test_reverse_urls(self):
        """Test that reverse URLs resolve to the correct paths."""
        self.assertEqual(self.list_url, '/api/red/items/')
        self.assertEqual(self.detail_url, f'/api/red/items/{self.item.pk}/')

    def test_create_red_item(self):
        """Test creating a new RedItem via the API."""
        data = {"name": "New Item", "description": "New Description"}
        response = self.client.post(self.list_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(RedItem.objects.count(), 2)
        self.assertEqual(RedItem.objects.latest('id').name, "New Item")

    def test_get_red_items_list(self):
        """Test retrieving the list of RedItems."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], self.item.name)

    def test_get_red_item_detail(self):
        """Test retrieving a single RedItem by ID."""
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.item.name)

    def test_update_red_item(self):
        """Test updating an existing RedItem."""
        data = {"name": "Updated Item", "description": "Updated Description"}
        response = self.client.put(self.detail_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Updated Item")

    def test_delete_red_item(self):
        """Test deleting a RedItem."""
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(RedItem.objects.count(), 0)
