import ApiService from '../services/ApiService';

// Mock fetch
global.fetch = jest.fn();
const mockFetch = fetch as jest.MockedFunction<typeof fetch>;

describe('ApiService', () => {
  beforeEach(() => {
    mockFetch.mockClear();
  });

  describe('getDashboardStats', () => {
    it('should return dashboard stats on successful API call', async () => {
      const mockStats = {
        totalEmails: 100,
        urgentEmails: 5,
        autoResponses: 20,
        processedToday: 15
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockStats,
      } as Response);

      const result = await ApiService.getDashboardStats();
      
      expect(result).toEqual(mockStats);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8081/api/dashboard/stats',
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should return mock data when API call fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const result = await ApiService.getDashboardStats();
      
      expect(result).toEqual({
        totalEmails: 156,
        urgentEmails: 3,
        autoResponses: 42,
        processedToday: 23,
      });
    });
  });

  describe('triggerEmailProcessing', () => {
    it('should trigger email processing successfully', async () => {
      const mockResult = {
        success: true,
        message: 'Processing started',
        processedCount: 5
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      } as Response);

      const result = await ApiService.triggerEmailProcessing();
      
      expect(result).toEqual(mockResult);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8081/api/emails/process',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });
  });

  describe('getEmails', () => {
    it('should return paginated emails on successful API call', async () => {
      const mockEmails = {
        content: [
          {
            id: '1',
            subject: 'Test Email',
            sender: 'test@example.com',
            receivedAt: '2023-01-01T00:00:00Z',
            priority: 'MEDIUM' as const,
            processed: true,
            requiresAttention: false,
            category: 'OTHER' as const,
            summary: 'Test summary',
          }
        ],
        totalElements: 1,
        totalPages: 1,
        first: true,
        last: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockEmails,
      } as Response);

      const result = await ApiService.getEmails(0, 20);
      
      expect(result).toEqual(mockEmails);
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8081/api/emails?page=0&size=20',
        expect.any(Object)
      );
    });
  });
});
