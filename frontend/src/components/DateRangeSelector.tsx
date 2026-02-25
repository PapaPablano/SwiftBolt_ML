import React from 'react';

export interface DateRangePreset {
  id: string;
  label: string;
  description: string;
  getDates: () => { startDate: Date; endDate: Date };
}

const getPresetDates = (preset: string): { startDate: Date; endDate: Date } => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  
  switch (preset) {
    case 'lastMonth':
      return { startDate: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000), endDate: today };
    case 'last3Months':
      return { startDate: new Date(today.getTime() - 90 * 24 * 60 * 60 * 1000), endDate: today };
    case 'last6Months':
      return { startDate: new Date(today.getTime() - 180 * 24 * 60 * 60 * 1000), endDate: today };
    case 'lastYear':
      return { startDate: new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000), endDate: today };
    case 'last2Years':
      return { startDate: new Date(today.getTime() - 730 * 24 * 60 * 60 * 1000), endDate: today };
    case 'last5Years':
      return { startDate: new Date(today.getTime() - 1825 * 24 * 60 * 60 * 1000), endDate: today };
    case 'dotComBubble':
      return { startDate: new Date('1995-01-01'), endDate: new Date('2000-03-10') };
    case 'dotComBust':
      return { startDate: new Date('2000-03-10'), endDate: new Date('2002-10-09') };
    case 'gfc':
      return { startDate: new Date('2007-12-01'), endDate: new Date('2009-06-01') };
    case 'postGfcExpansion':
      return { startDate: new Date('2009-06-01'), endDate: new Date('2020-02-19') };
    case 'covidCrash':
      return { startDate: new Date('2020-02-19'), endDate: new Date('2020-03-23') };
    case 'covidRebound':
      return { startDate: new Date('2020-03-23'), endDate: new Date('2020-08-31') };
    case 'rateHikeBear2022':
      return { startDate: new Date('2022-01-03'), endDate: new Date('2022-10-15') };
    case 'aiBull2022_2024':
      return { startDate: new Date('2022-10-12'), endDate: new Date('2024-01-19') };
    default:
      return { startDate: new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000), endDate: today };
  }
};

export const datePresets = [
  { id: 'lastMonth', label: 'Last Month', description: 'Last 30 days', category: 'recent' },
  { id: 'last3Months', label: 'Last 3 Months', description: 'Last 90 days', category: 'recent' },
  { id: 'last6Months', label: 'Last 6 Months', description: 'Last 180 days', category: 'recent' },
  { id: 'lastYear', label: 'Last Year', description: 'Last 365 days', category: 'recent' },
  { id: 'last2Years', label: 'Last 2 Years', description: 'Last 730 days', category: 'recent' },
  { id: 'last5Years', label: 'Last 5 Years', description: 'Last 1825 days', category: 'recent' },
  { id: 'dotComBubble', label: 'Dot-com Bubble', description: '1995-2000', category: 'regime' },
  { id: 'dotComBust', label: 'Dot-com Bust', description: '2000-2002', category: 'regime' },
  { id: 'gfc', label: 'GFC', description: '2007-2009', category: 'regime' },
  { id: 'postGfcExpansion', label: 'Post-GFC Expansion', description: '2009-2020', category: 'regime' },
  { id: 'covidCrash', label: 'COVID Crash', description: 'Feb-Mar 2020', category: 'regime' },
  { id: 'covidRebound', label: 'COVID Rebound', description: 'Mar-Aug 2020', category: 'regime' },
  { id: 'rateHikeBear2022', label: '2022 Bear Market', description: 'Rate hike cycle', category: 'regime' },
  { id: 'aiBull2022_2024', label: 'AI Bull', description: '2022-2024', category: 'regime' },
];

interface DateRangeSelectorProps {
  startDate: Date;
  endDate: Date;
  onStartDateChange: (date: Date) => void;
  onEndDateChange: (date: Date) => void;
}

export const DateRangeSelector: React.FC<DateRangeSelectorProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}) => {
  const [selectedPreset, setSelectedPreset] = React.useState<string | null>(null);
  const [showCustom, setShowCustom] = React.useState(false);

  const recentPresets = datePresets.filter(p => p.category === 'recent');
  const regimePresets = datePresets.filter(p => p.category === 'regime');

  const handlePresetSelect = (presetId: string) => {
    const dates = getPresetDates(presetId);
    onStartDateChange(dates.startDate);
    onEndDateChange(dates.endDate);
    setSelectedPreset(presetId);
    setShowCustom(false);
  };

  const handleCustomDateChange = (type: 'start' | 'end', value: string) => {
    const date = new Date(value);
    if (type === 'start') {
      onStartDateChange(date);
    } else {
      onEndDateChange(date);
    }
    setSelectedPreset(null);
  };

  const formatDateForInput = (date: Date): string => {
    return date.toISOString().split('T')[0];
  };

  return (
    <div className="space-y-4">
      {/* Quick Settings Label */}
      <div className="text-sm font-medium text-gray-300">Quick Settings</div>
      
      {/* Recent Presets */}
      <div className="flex flex-wrap gap-2">
        {recentPresets.map((preset) => (
          <button
            key={preset.id}
            onClick={() => handlePresetSelect(preset.id)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              selectedPreset === preset.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
            title={preset.description}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Market Regimes Label */}
      <div className="text-sm font-medium text-gray-300 pt-2">Market Regimes</div>
      
      {/* Regime Presets */}
      <div className="flex flex-wrap gap-2">
        {regimePresets.map((preset) => (
          <button
            key={preset.id}
            onClick={() => handlePresetSelect(preset.id)}
            className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
              selectedPreset === preset.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
            }`}
            title={preset.description}
          >
            {preset.label}
          </button>
        ))}
      </div>

      {/* Custom Range Toggle */}
      <div className="pt-2">
        <button
          onClick={() => setShowCustom(!showCustom)}
          className="text-xs text-blue-400 hover:text-blue-300 underline"
        >
          {showCustom ? 'Hide Custom Range' : 'Use Custom Range'}
        </button>
      </div>

      {/* Custom Date Pickers */}
      {showCustom && (
        <div className="flex gap-4 pt-2">
          <div className="flex-1">
            <label className="block text-xs text-gray-400 mb-1">Start Date</label>
            <input
              type="date"
              value={formatDateForInput(startDate)}
              onChange={(e) => handleCustomDateChange('start', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-800 text-white border border-gray-700 rounded-md focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex-1">
            <label className="block text-xs text-gray-400 mb-1">End Date</label>
            <input
              type="date"
              value={formatDateForInput(endDate)}
              onChange={(e) => handleCustomDateChange('end', e.target.value)}
              className="w-full px-3 py-2 text-sm bg-gray-800 text-white border border-gray-700 rounded-md focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Selected Preset Info */}
      {selectedPreset && (
        <div className="text-xs text-gray-400 pt-2">
          {datePresets.find(p => p.id === selectedPreset)?.description}
        </div>
      )}
    </div>
  );
};

export { getPresetDates };
