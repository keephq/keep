import { getNestedValue } from "../object-utils";

describe("object-utils", () => {
  describe("getNestedValue", () => {
    it("should return the value for a simple property path", () => {
      const obj = { name: "John", age: 30 };
      expect(getNestedValue(obj, "name")).toBe("John");
      expect(getNestedValue(obj, "age")).toBe(30);
    });

    it("should return the value for a nested property path", () => {
      const obj = { 
        user: { 
          name: "John", 
          address: { 
            city: "New York", 
            zipCode: 10001 
          } 
        } 
      };
      expect(getNestedValue(obj, "user.name")).toBe("John");
      expect(getNestedValue(obj, "user.address.city")).toBe("New York");
      expect(getNestedValue(obj, "user.address.zipCode")).toBe(10001);
    });

    it("should handle arrays in object path", () => {
      const obj = { 
        users: [
          { id: 1, name: "John" },
          { id: 2, name: "Jane" }
        ],
        settings: {
          notifications: [
            { type: "email", enabled: true },
            { type: "sms", enabled: false }
          ]
        }
      };
      expect(getNestedValue(obj, "users.0.name")).toBe("John");
      expect(getNestedValue(obj, "users.1.name")).toBe("Jane");
      expect(getNestedValue(obj, "settings.notifications.0.enabled")).toBe(true);
      expect(getNestedValue(obj, "settings.notifications.1.enabled")).toBe(false);
    });
    
    it("should handle numeric keys for both arrays and objects", () => {
      const obj = {
        "0": "Zero index in object",
        "1": "First index in object",
        items: [
          "Zero index in array",
          "First index in array"
        ],
        nested: {
          "0": "Nested zero index",
          "42": "Answer to everything"
        }
      };
      
      expect(getNestedValue(obj, "0")).toBe("Zero index in object");
      expect(getNestedValue(obj, "1")).toBe("First index in object");
      expect(getNestedValue(obj, "items.0")).toBe("Zero index in array");
      expect(getNestedValue(obj, "items.1")).toBe("First index in array");
      expect(getNestedValue(obj, "nested.0")).toBe("Nested zero index");
      expect(getNestedValue(obj, "nested.42")).toBe("Answer to everything");
    });
    
    it("should handle property names with special characters", () => {
      const obj = {
        "@user": "twitter handle",
        "#tag": "hashtag",
        "$price": 100,
        "user-name": "hyphenated",
        "nested": {
          "field+plus": "plus character",
          "field&amp": "ampersand",
          "field*star": "asterisk"
        }
      };
      
      expect(getNestedValue(obj, "@user")).toBe("twitter handle");
      expect(getNestedValue(obj, "#tag")).toBe("hashtag");
      expect(getNestedValue(obj, "$price")).toBe(100);
      expect(getNestedValue(obj, "user-name")).toBe("hyphenated");
      expect(getNestedValue(obj, "nested.field+plus")).toBe("plus character");
      expect(getNestedValue(obj, "nested.field&amp")).toBe("ampersand");
      expect(getNestedValue(obj, "nested.field*star")).toBe("asterisk");
    });

    it("should handle values with special characters", () => {
      const obj = {
        "special.key": "special value",
        nested: {
          "key.with.dots": "dotted value"
        }
      };
      // Direct access to properties with dots in their names
      expect(getNestedValue(obj, "special.key")).toBe(undefined); // Will try to get obj.special.key which doesn't exist
      expect(getNestedValue(obj, "nested.key.with.dots")).toBe(undefined); // Same issue
    });
    
    it("should handle non-ASCII property names", () => {
      const obj = {
        "résumé": "CV document",
        "información": {
          "título": "Test Title",
          "descripción": "Test Description"
        },
        "数据": {
          "名称": "Test Name"
        }
      };
      
      expect(getNestedValue(obj, "résumé")).toBe("CV document");
      expect(getNestedValue(obj, "información.título")).toBe("Test Title");
      expect(getNestedValue(obj, "información.descripción")).toBe("Test Description");
      expect(getNestedValue(obj, "数据.名称")).toBe("Test Name");
    });
    
    it("should handle property names with spaces", () => {
      const obj = {
        "user name": "John Doe",
        "contact info": {
          "phone number": "123-456-7890",
          "email address": "john@example.com"
        }
      };
      
      expect(getNestedValue(obj, "user name")).toBe("John Doe");
      expect(getNestedValue(obj, "contact info.phone number")).toBe("123-456-7890");
      expect(getNestedValue(obj, "contact info.email address")).toBe("john@example.com");
    });

    it("should return undefined for non-existent paths", () => {
      const obj = { user: { name: "John" } };
      expect(getNestedValue(obj, "user.age")).toBe(undefined);
      expect(getNestedValue(obj, "profile.image")).toBe(undefined);
      expect(getNestedValue(obj, "unknown")).toBe(undefined);
    });

    it("should handle edge cases", () => {
      // Empty object
      expect(getNestedValue({}, "name")).toBe(undefined);
      
      // Empty path
      expect(getNestedValue({ name: "John" }, "")).toBe(undefined);
      
      // Null or undefined object
      expect(getNestedValue(null, "name")).toBe(undefined);
      expect(getNestedValue(undefined, "name")).toBe(undefined);
      
      // Null or undefined path
      expect(getNestedValue({ name: "John" }, null as any)).toBe(undefined);
      expect(getNestedValue({ name: "John" }, undefined as any)).toBe(undefined);
      
      // Various value types
      const obj = {
        nullValue: null,
        undefinedValue: undefined,
        zeroValue: 0,
        falseValue: false,
        emptyString: "",
        emptyArray: [],
        emptyObject: {}
      };
      
      expect(getNestedValue(obj, "nullValue")).toBe(null);
      expect(getNestedValue(obj, "undefinedValue")).toBe(undefined);
      expect(getNestedValue(obj, "zeroValue")).toBe(0);
      expect(getNestedValue(obj, "falseValue")).toBe(false);
      expect(getNestedValue(obj, "emptyString")).toBe("");
      expect(getNestedValue(obj, "emptyArray")).toEqual([]);
      expect(getNestedValue(obj, "emptyObject")).toEqual({});
    });
    
    it("should handle property access on primitive values", () => {
      // Attempt to navigate through non-object values
      expect(getNestedValue("string", "length")).toBe(undefined);
      expect(getNestedValue(42, "toString")).toBe(undefined);
      expect(getNestedValue(true, "valueOf")).toBe(undefined);
      
      // Nested path through non-object
      const obj = { value: 123 };
      expect(getNestedValue(obj, "value.toString")).toBe(undefined);
    });
    
    it("should handle missing middle segments in path", () => {
      const obj = { user: { name: "John" } };
      
      // Missing middle segments
      expect(getNestedValue(obj, "user.profile.image")).toBe(undefined);
      expect(getNestedValue(obj, "metadata.host.name")).toBe(undefined);
      
      // Attempt to navigate through null/undefined values
      const objWithNull = { 
        user: null, 
        settings: { notifications: undefined }
      };
      expect(getNestedValue(objWithNull, "user.name")).toBe(undefined);
      expect(getNestedValue(objWithNull, "settings.notifications.email")).toBe(undefined);
    });
    
    it("should respect case sensitivity in property names", () => {
      const obj = {
        User: "John",
        user: "Jane", 
        nested: {
          Name: "Smith",
          name: "Jones",
          ADDRESS: {
            City: "New York"
          },
          address: {
            city: "Boston"
          }
        },
        Items: ["A", "B", "C"],
        items: ["X", "Y", "Z"]
      };
      
      // Test case sensitivity in property names
      expect(getNestedValue(obj, "User")).toBe("John");
      expect(getNestedValue(obj, "user")).toBe("Jane");
      expect(getNestedValue(obj, "USER")).toBe(undefined);
      
      // Test case sensitivity in nested property names
      expect(getNestedValue(obj, "nested.Name")).toBe("Smith");
      expect(getNestedValue(obj, "nested.name")).toBe("Jones");
      expect(getNestedValue(obj, "nested.NAME")).toBe(undefined);
      
      // Test case sensitivity in deeply nested property paths
      expect(getNestedValue(obj, "nested.ADDRESS.City")).toBe("New York");
      expect(getNestedValue(obj, "nested.address.city")).toBe("Boston");
      expect(getNestedValue(obj, "nested.ADDRESS.city")).toBe(undefined);
      expect(getNestedValue(obj, "nested.address.City")).toBe(undefined);
      
      // Test case sensitivity with arrays
      expect(getNestedValue(obj, "Items.0")).toBe("A");
      expect(getNestedValue(obj, "items.0")).toBe("X");
    });

    it("should handle alert and dashboard widget use cases", () => {
      // Simulate alert object structure
      const alert = {
        id: "alert-123",
        name: "High CPU Usage",
        severity: "critical",
        annotations: {
          summary: "CPU usage is above 90%",
          details: "Server XYZ has high CPU usage"
        },
        metadata: {
          host: {
            name: "server-xyz",
            ip: "192.168.1.100"
          }
        }
      };
      
      expect(getNestedValue(alert, "id")).toBe("alert-123");
      expect(getNestedValue(alert, "severity")).toBe("critical");
      expect(getNestedValue(alert, "annotations.summary")).toBe("CPU usage is above 90%");
      expect(getNestedValue(alert, "metadata.host.name")).toBe("server-xyz");
      expect(getNestedValue(alert, "metadata.host.ip")).toBe("192.168.1.100");
      expect(getNestedValue(alert, "metadata.service")).toBe(undefined);
    });
  });
});