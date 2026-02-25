//
//  StrategyBuilderView.swift
//  SwiftBoltML
//
//  Created by SwiftBolt
//

import SwiftUI

struct StrategyBuilderView: View {
    @State private var strategyName = ""
    @State private var strategyDescription = ""
    @State private var selectedIndicator = "RSI"
    @State private var parameterValue = "14"
    
    @State private var showingParameterConfig = false
    @State private var showingSaveConfirmation = false
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Strategy Information")) {
                    TextField("Strategy Name", text: $strategyName)
                    
                    TextEditor(text: $strategyDescription)
                        .frame(height: 100)
                }
                
                Section(header: Text("Parameters")) {
                    HStack {
                        Text("Indicator")
                        Spacer()
                        Text(selectedIndicator)
                            .foregroundColor(.secondary)
                    }
                    .onTapGesture {
                        showingParameterConfig = true
                    }
                    
                    HStack {
                        Text("Parameter Value")
                        Spacer()
                        Text(parameterValue)
                            .foregroundColor(.secondary)
                    }
                    .onTapGesture {
                        showingParameterConfig = true
                    }
                }
                
                Section(header: Text("Indicators")) {
                    ForEach(["RSI", "MACD", "Bollinger Bands", "Moving Average"], id: \.self) { indicator in
                        HStack {
                            Text(indicator)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .foregroundColor(.secondary)
                                .imageScale(.small)
                        }
                    }
                }
                
                Section(header: Text("Backtesting")) {
                    HStack {
                        Text("Enable Backtesting")
                        Spacer()
                        Toggle("", isOn: .constant(true))
                    }
                    .padding(.vertical, 4)
                    
                    HStack {
                        Text("Strategy Type")
                        Spacer()
                        Picker("", selection: .constant("Simple")) {
                            Text("Simple").tag("Simple")
                            Text("Advanced").tag("Advanced")
                        }
                        .pickerStyle(MenuPickerStyle())
                    }
                }
            }
            .navigationTitle("Strategy Builder")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        showingSaveConfirmation = true
                    }
                    .disabled(strategyName.isEmpty)
                }
            }
            .alert("Save Strategy", isPresented: $showingSaveConfirmation) {
                Button("Confirm") {
                    // Save logic would go here
                }
                Button("Cancel") { }
            } message: {
                Text("Are you sure you want to save this strategy?")
            }
            .sheet(isPresented: $showingParameterConfig) {
                ParameterConfigView()
                    .frame(minWidth: 400, minHeight: 300)
            }
        }
    }
}

struct ParameterConfigView: View {
    @State private var parameterValue = "14"
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Parameter Configuration")) {
                    TextField("Parameter Value", text: $parameterValue)
                }
                
                Section(header: Text("Help")) {
                    Text("Enter the parameter value for the selected indicator.")
                        .foregroundColor(.secondary)
                        .font(.caption)
                }
            }
            .navigationTitle("Configure Parameter")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

struct StrategyBuilderView_Previews: PreviewProvider {
    static var previews: some View {
        StrategyBuilderView()
    }
}