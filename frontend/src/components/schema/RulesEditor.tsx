"use client";

import { useState } from "react";

export interface Rules {
  spend?: { min?: number; max?: number };
  clicks?: { min?: number; max?: number };
  conversions?: { min?: number; max?: number };
  campaign?: { minLength?: number; maxLength?: number };
  channel?: {
    minLength?: number;
    maxLength?: number;
    allowed?: string[];
  };
  date?: { minDate?: string; maxDate?: string };
}

interface RulesEditorProps {
  rules: Rules;
  onChange: (rules: Rules) => void;
}

export function RulesEditor({ rules, onChange }: RulesEditorProps) {
  const [localRules, setLocalRules] = useState<Rules>(rules);

  const updateRule = (field: keyof Rules, updates: any) => {
    const newRules = { ...localRules, [field]: { ...localRules[field], ...updates } };
    setLocalRules(newRules);
    onChange(newRules);
  };

  const removeRule = (field: keyof Rules) => {
    const newRules = { ...localRules };
    delete newRules[field];
    setLocalRules(newRules);
    onChange(newRules);
  };

  return (
    <div className="space-y-6" data-testid="schema-rules-editor">
      <h3 className="text-lg font-semibold">Validation Rules</h3>

      {/* Numeric rules */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm text-gray-700">Numeric Fields</h4>

        {/* Spend */}
        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Spend</label>
            <button
              type="button"
              onClick={() => removeRule("spend")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Min</label>
              <input
                type="number"
                value={localRules.spend?.min ?? ""}
                onChange={(e) =>
                  updateRule("spend", { min: e.target.value ? Number(e.target.value) : undefined })
                }
                placeholder="0"
                className="w-full px-2 py-1 border rounded text-sm"
                data-testid="schema-rules-spend-min"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Max</label>
              <input
                type="number"
                value={localRules.spend?.max ?? ""}
                onChange={(e) =>
                  updateRule("spend", { max: e.target.value ? Number(e.target.value) : undefined })
                }
                placeholder="1000000"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>

        {/* Clicks */}
        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Clicks</label>
            <button
              type="button"
              onClick={() => removeRule("clicks")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Min</label>
              <input
                type="number"
                value={localRules.clicks?.min ?? ""}
                onChange={(e) =>
                  updateRule("clicks", { min: e.target.value ? Number(e.target.value) : undefined })
                }
                placeholder="0"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Max</label>
              <input
                type="number"
                value={localRules.clicks?.max ?? ""}
                onChange={(e) =>
                  updateRule("clicks", { max: e.target.value ? Number(e.target.value) : undefined })
                }
                placeholder="10000000"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>

        {/* Conversions */}
        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Conversions</label>
            <button
              type="button"
              onClick={() => removeRule("conversions")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Min</label>
              <input
                type="number"
                value={localRules.conversions?.min ?? ""}
                onChange={(e) =>
                  updateRule("conversions", {
                    min: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                placeholder="0"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Max</label>
              <input
                type="number"
                value={localRules.conversions?.max ?? ""}
                onChange={(e) =>
                  updateRule("conversions", {
                    max: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                placeholder="1000000"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>
      </div>

      {/* String rules */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm text-gray-700">String Fields</h4>

        {/* Campaign */}
        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Campaign</label>
            <button
              type="button"
              onClick={() => removeRule("campaign")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Min Length</label>
              <input
                type="number"
                value={localRules.campaign?.minLength ?? ""}
                onChange={(e) =>
                  updateRule("campaign", {
                    minLength: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                placeholder="1"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Max Length</label>
              <input
                type="number"
                value={localRules.campaign?.maxLength ?? ""}
                onChange={(e) =>
                  updateRule("campaign", {
                    maxLength: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                placeholder="200"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>

        {/* Channel */}
        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Channel</label>
            <button
              type="button"
              onClick={() => removeRule("channel")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-600 mb-1">Min Length</label>
                <input
                  type="number"
                  value={localRules.channel?.minLength ?? ""}
                  onChange={(e) =>
                    updateRule("channel", {
                      minLength: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  placeholder="1"
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-600 mb-1">Max Length</label>
                <input
                  type="number"
                  value={localRules.channel?.maxLength ?? ""}
                  onChange={(e) =>
                    updateRule("channel", {
                      maxLength: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  placeholder="200"
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Allowed Values (comma-separated)</label>
              <input
                type="text"
                value={localRules.channel?.allowed?.join(", ") ?? ""}
                onChange={(e) => {
                  const allowed = e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  updateRule("channel", { allowed: allowed.length > 0 ? allowed : undefined });
                }}
                placeholder="Search, Social, Display, Email, Other"
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Date rules */}
      <div className="space-y-4">
        <h4 className="font-medium text-sm text-gray-700">Date Field</h4>

        <div className="border rounded p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="font-medium">Date</label>
            <button
              type="button"
              onClick={() => removeRule("date")}
              className="text-xs text-red-600 hover:text-red-800"
            >
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-gray-600 mb-1">Min Date</label>
              <input
                type="date"
                value={localRules.date?.minDate ?? ""}
                onChange={(e) => updateRule("date", { minDate: e.target.value || undefined })}
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">Max Date</label>
              <input
                type="date"
                value={localRules.date?.maxDate ?? ""}
                onChange={(e) => updateRule("date", { maxDate: e.target.value || undefined })}
                className="w-full px-2 py-1 border rounded text-sm"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
