import logging
import math
from typing import Dict, List, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)

class CoinJoinDetectionHeuristic:
    """
    Detects CoinJoin transactions from major mixing services
    Based on the JoinDetect framework and service-specific patterns
    Enhanced with formal mathematical conditions from academic research
    """
    
    def __init__(self):
        self.confidence_threshold = 0.7  # Minimum confidence for positive detection
        
        # Configuration parameters (made configurable as per roadmap)
        self.config = {
            # Whirlpool pools (denomination_btc, fee_btc)
            'whirlpool_pools': [
                (0.001, 0.00005),   # 0.001 BTC pool
                (0.01, 0.0005),     # 0.01 BTC pool  
                (0.05, 0.00175),    # 0.05 BTC pool
                (0.5, 0.0175),      # 0.5 BTC pool
            ],
            
            # Wasabi parameters
            'wasabi_1_0': {
                'target_denomination_btc': 0.1,
                'epsilon_btc': 0.01,  # tolerance
                'amax': 10  # max inputs per participant
            },
            'wasabi_1_1': {
                'target_denomination_btc': 0.1,
                'epsilon_btc': 0.01,
                'amax': 10,
                'max_mixing_level': 3  # L parameter
            },
            'wasabi_2_0': {
                'denominations_satoshis': [50000, 100000, 200000, 500000, 1000000, 2000000, 5000000, 10000000],  # Fixed denominations
                'amax': 10,
                'p': 50,  # target input count
                'vmin': 5000  # minimum input value
            },
            
            # Whirlpool parameters
            'whirlpool_tx0': {
                'amax': 70,
                'eta1': 0.5,  # coordinator fee range
                'eta2': 3.0,
                'epsilon_min': 100,  # satoshis
                'epsilon_max': 100000
            },
            'whirlpool_mix': {
                'epsilon_max': 100000  # satoshis
            }
        }
        
    def analyze_transaction(self, tx_data: Dict) -> Dict:
        """
        Main entry point for CoinJoin analysis with enhanced detection methods
        
        Args:
            tx_data: Transaction data from Blockstream API format
            
        Returns:
            Dict with detection results including participant count and denomination
        """
        try:
            # Extract transaction structure
            inputs = tx_data.get('vin', [])
            outputs = tx_data.get('vout', [])
            
            if len(inputs) < 2 or len(outputs) < 2:
                return self._negative_result("Insufficient inputs/outputs for CoinJoin")
            
            # Enhanced analysis data with script analysis
            input_amounts = self._extract_input_amounts(inputs)
            output_amounts = self._extract_output_amounts(outputs)
            input_scripts = self._extract_input_scripts(inputs)
            output_scripts = self._extract_output_scripts(outputs)
            
            # Skip if we can't analyze properly
            if not input_amounts or not output_amounts:
                return self._negative_result("Unable to extract transaction amounts")
            
            # Calculate script metrics (key for mathematical conditions)
            nscripts_in = len(set(input_scripts)) if input_scripts else 0
            nscripts_out = len(set(output_scripts)) if output_scripts else 0
            
            analysis_data = {
                'input_count': len(inputs),
                'output_count': len(outputs),
                'input_amounts': input_amounts,
                'output_amounts': output_amounts,
                'input_scripts': input_scripts,
                'output_scripts': output_scripts,
                'nscripts_in': nscripts_in,
                'nscripts_out': nscripts_out,
                'total_input': sum(input_amounts),
                'total_output': sum(output_amounts)
            }
            
            # Run enhanced detection methods
            joinmarket_result = self.detect_joinmarket_v2(analysis_data)
            wasabi_1_0_result = self.detect_wasabi_1_0(analysis_data)
            wasabi_1_1_result = self.detect_wasabi_1_1(analysis_data) 
            wasabi_2_0_result = self.detect_wasabi_2_0(analysis_data)
            whirlpool_tx0_result = self.detect_whirlpool_tx0(analysis_data)
            whirlpool_mix_result = self.detect_whirlpool_mix(analysis_data)
            
            # Determine best match with enhanced types
            results = [
                ('joinmarket', joinmarket_result),
                ('wasabi_1_0', wasabi_1_0_result),
                ('wasabi_1_1', wasabi_1_1_result),
                ('wasabi_2_0', wasabi_2_0_result),
                ('whirlpool_tx0', whirlpool_tx0_result),
                ('whirlpool_mix', whirlpool_mix_result)
            ]
            
            # Find highest confidence detection above threshold
            best_match = None
            best_confidence = 0
            
            for service_type, result in results:
                if result['confidence'] > best_confidence and result['confidence'] >= self.confidence_threshold:
                    best_confidence = result['confidence']
                    best_match = (service_type, result)
            
            if best_match:
                service_type, result = best_match
                return {
                    'is_coinjoin': True,
                    'coinjoin_type': service_type,
                    'confidence': result['confidence'],
                    'coinjoin_participants': result.get('participants', None),
                    'coinjoin_denomination': result.get('denomination', None),
                    'analysis': {
                        'detected_service': service_type,
                        'service_analysis': result,
                        'transaction_structure': analysis_data,
                        'all_detections': {svc: res for svc, res in results}
                    }
                }
            else:
                return self._negative_result("No CoinJoin pattern detected above threshold", analysis_data)
                
        except Exception as e:
            logger.error(f"Error analyzing transaction for CoinJoin: {e}")
            return self._negative_result(f"Analysis error: {str(e)}")
    
    def detect_joinmarket(self, analysis_data: Dict) -> Dict:
        """
        Detect JoinMarket transactions
        
        JoinMarket characteristics:
        - Variable number of inputs and outputs
        - No fixed denominations
        - n >= |Δout|/2 where n is number of equal outputs
        - 3 <= n <= number of input scripts
        """
        try:
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            
            # Count equal output amounts (with small tolerance for fees)
            tolerance = 1000  # 1000 satoshis tolerance
            equal_output_groups = self._group_similar_amounts(outputs, tolerance)
            
            # Find largest group of equal outputs
            largest_group_size = max(len(group) for group in equal_output_groups) if equal_output_groups else 0
            
            # JoinMarket condition: n >= |Δout|/2
            delta_out = len(set(outputs))  # Number of distinct output amounts
            condition1 = largest_group_size >= delta_out / 2
            
            # Additional conditions
            condition2 = 3 <= largest_group_size <= len(inputs)
            condition3 = len(inputs) >= 2 and len(outputs) >= 3
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Equal outputs condition met: {largest_group_size} >= {delta_out/2}")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"Input/output count condition met: 3 <= {largest_group_size} <= {len(inputs)}")
            
            if condition3:
                confidence += 0.2
                reasons.append("Minimum transaction complexity met")
            
            # Bonus for irregular patterns typical of JoinMarket
            if len(set(outputs)) > len(set(inputs)):
                confidence += 0.1
                reasons.append("Output diversity suggests JoinMarket flexibility")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'largest_equal_group': largest_group_size,
                'delta_out': delta_out,
                'conditions_met': [condition1, condition2, condition3]
            }
            
        except Exception as e:
            logger.error(f"Error in JoinMarket detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def detect_wasabi_v1(self, analysis_data: Dict) -> Dict:
        """
        Detect Wasabi v1 transactions
        
        Wasabi v1 characteristics:
        - Multiple outputs around 0.1 BTC (10M satoshis)
        - n <= number of input scripts <= |Δin| <= amax × n
        - Coordinator fee structure
        """
        try:
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            
            # Check for 0.1 BTC denominations (with tolerance for fees)
            target_amount = self.wasabi_v1_denomination
            tolerance = 100000  # 100k satoshis tolerance for fees
            
            wasabi_outputs = [amt for amt in outputs 
                            if abs(amt - target_amount) <= tolerance]
            
            # Count equal outputs around 0.1 BTC
            equal_outputs_count = len(wasabi_outputs)
            
            confidence = 0.0
            reasons = []
            
            # Primary condition: multiple 0.1 BTC outputs
            if equal_outputs_count >= 2:
                confidence += 0.5
                reasons.append(f"Found {equal_outputs_count} outputs around 0.1 BTC")
            
            # Additional Wasabi v1 conditions
            delta_in = len(set(inputs))
            condition1 = equal_outputs_count <= len(inputs)
            condition2 = len(inputs) <= delta_in
            
            if condition1:
                confidence += 0.2
                reasons.append("Input count condition met")
            
            if condition2:
                confidence += 0.1
                reasons.append("Input diversity condition met")
            
            # Check for coordinator fee pattern (small additional outputs)
            small_outputs = [amt for amt in outputs if amt < 1000000]  # < 0.01 BTC
            if small_outputs and equal_outputs_count >= 2:
                confidence += 0.2
                reasons.append("Small outputs suggest coordinator fees")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'wasabi_outputs_count': equal_outputs_count,
                'target_denomination': target_amount,
                'small_outputs_count': len(small_outputs)
            }
            
        except Exception as e:
            logger.error(f"Error in Wasabi detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def detect_whirlpool(self, analysis_data: Dict) -> Dict:
        """
        Detect Whirlpool (Samourai) transactions
        
        Whirlpool characteristics:
        - Fixed denominations: 0.001, 0.01 BTC
        - Exactly 5 inputs and 5 outputs (classic)
        - Very precise amount matching
        """
        try:
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            
            confidence = 0.0
            reasons = []
            detected_denomination = None
            
            # Check for known Whirlpool denominations
            for denomination in self.whirlpool_denominations:
                matching_outputs = [amt for amt in outputs if amt == denomination]
                
                if len(matching_outputs) >= 2:
                    confidence += 0.6
                    detected_denomination = denomination
                    reasons.append(f"Found {len(matching_outputs)} outputs of exact denomination {denomination/100000000:.3f} BTC")
                    break
            
            # Classic Whirlpool structure: 5 inputs, 5 outputs
            if len(inputs) == 5 and len(outputs) == 5:
                confidence += 0.3
                reasons.append("Classic 5x5 Whirlpool structure")
            elif 3 <= len(inputs) <= 8 and 3 <= len(outputs) <= 8:
                confidence += 0.1
                reasons.append("Whirlpool-compatible structure")
            
            # Very precise amount matching (no tolerance)
            equal_output_groups = self._group_similar_amounts(outputs, tolerance=0)
            max_group_size = max(len(group) for group in equal_output_groups) if equal_output_groups else 0
            
            if max_group_size >= len(outputs) * 0.6:  # 60% of outputs are identical
                confidence += 0.1
                reasons.append("High output amount uniformity")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'detected_denomination': detected_denomination,
                'structure': f"{len(inputs)}x{len(outputs)}",
                'max_equal_outputs': max_group_size
            }
            
        except Exception as e:
            logger.error(f"Error in Whirlpool detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def _extract_input_amounts(self, inputs: List[Dict]) -> List[int]:
        """Extract input amounts from vin array"""
        amounts = []
        for inp in inputs:
            prevout = inp.get('prevout')
            if prevout:
                amounts.append(prevout.get('value', 0))
        return amounts
    
    def _extract_output_amounts(self, outputs: List[Dict]) -> List[int]:
        """Extract output amounts from vout array"""
        return [out.get('value', 0) for out in outputs]
    
    def _extract_input_scripts(self, inputs: List[Dict]) -> List[str]:
        """Extract input scripts for nscripts_in calculation"""
        scripts = []
        for inp in inputs:
            prevout = inp.get('prevout')
            if prevout:
                scriptpubkey = prevout.get('scriptpubkey', '')
                scripts.append(scriptpubkey)
        return scripts
    
    def _extract_output_scripts(self, outputs: List[Dict]) -> List[str]:
        """Extract output scripts for nscripts_out calculation"""
        scripts = []
        for out in outputs:
            scriptpubkey = out.get('scriptpubkey', '')
            scripts.append(scriptpubkey)
        return scripts

    def detect_joinmarket_v2(self, analysis_data: Dict) -> Dict:
        """
        Enhanced JoinMarket detection with precise mathematical conditions
        Based on formal academic specifications from the roadmap
        
        Mathematical Conditions:
        1. n >= |∆out| / 2  (where n = number of participants)
        2. 3 <= nscripts_in
        3. |∆out| = nscripts_out
        """
        try:
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            nscripts_in = analysis_data['nscripts_in']
            nscripts_out = analysis_data['nscripts_out']
            
            # Estimate n (number of participants) from equal output groups
            value_counts = {}
            for val in outputs:
                value_counts[val] = value_counts.get(val, 0) + 1
            
            if not value_counts:
                return {'confidence': 0.0, 'error': 'No output values found'}
            
            n_estimated = max(value_counts.values())
            delta_out = len(outputs)
            
            # Mathematical Condition 1: n >= |∆out| / 2
            condition1 = n_estimated >= delta_out / 2
            
            # Mathematical Condition 2: 3 <= nscripts_in
            condition2 = nscripts_in >= 3
            
            # Mathematical Condition 3: |∆out| = nscripts_out  
            condition3 = delta_out == nscripts_out
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Condition 1 met: n={n_estimated} >= |∆out|/2={delta_out/2}")
            
            if condition2:
                confidence += 0.4
                reasons.append(f"Condition 2 met: nscripts_in={nscripts_in} >= 3")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Condition 3 met: |∆out|={delta_out} = nscripts_out={nscripts_out}")
            
            # Find the denomination for the largest equal group
            denomination = None
            for val, count in value_counts.items():
                if count == n_estimated:
                    denomination = val
                    break
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': n_estimated,
                'denomination': denomination,
                'conditions_met': [condition1, condition2, condition3],
                'mathematical_analysis': {
                    'n_estimated': n_estimated,
                    'delta_out': delta_out,
                    'nscripts_in': nscripts_in,
                    'nscripts_out': nscripts_out,
                    'condition_1_check': f"{n_estimated} >= {delta_out}/2 = {condition1}",
                    'condition_2_check': f"{nscripts_in} >= 3 = {condition2}",
                    'condition_3_check': f"{delta_out} == {nscripts_out} = {condition3}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error in enhanced JoinMarket detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}

    def detect_wasabi_1_0(self, analysis_data: Dict) -> Dict:
        """
        Enhanced Wasabi 1.0 detection with ZeroLink protocol conditions
        
        Mathematical Conditions:
        1. Post-mix denomination: 0.1 - ε <= d_hat <= 0.1 + ε BTC
        2. Input/output constraints: n_estimated <= nscripts_in <= |∆in| <= amax * n_estimated  
        3. Output count: n_estimated >= (|∆out| - 1) / 2
        4. Unique output scripts: |∆out| = nscripts_out
        """
        try:
            config = self.config['wasabi_1_0']
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            nscripts_in = analysis_data['nscripts_in']
            nscripts_out = analysis_data['nscripts_out']
            
            # Convert parameters to satoshis
            target_denomination_satoshis = int(config['target_denomination_btc'] * 10**8)
            epsilon_satoshis = int(config['epsilon_btc'] * 10**8)
            amax = config['amax']
            
            # Estimate n and d
            value_counts = {}
            for val in outputs:
                value_counts[val] = value_counts.get(val, 0) + 1
            
            if not value_counts:
                return {'confidence': 0.0, 'error': 'No output values found'}
            
            n_estimated = max(value_counts.values())
            
            # Find possible denominations (values with max count)
            d_possible_denominations = {val for val, count in value_counts.items() if count == n_estimated}
            
            # Find d_hat (closest to 0.1 BTC)
            d_hat = min(d_possible_denominations, 
                       key=lambda x: abs(x - target_denomination_satoshis))
            
            # Mathematical Condition 1: Denomination near 0.1 BTC
            condition1 = (target_denomination_satoshis - epsilon_satoshis <= d_hat <= 
                         target_denomination_satoshis + epsilon_satoshis)
            
            # Mathematical Condition 2: Input/output constraints
            num_inputs = len(inputs)
            condition2 = (n_estimated <= nscripts_in and 
                         nscripts_in <= num_inputs and 
                         num_inputs <= amax * n_estimated)
            
            # Mathematical Condition 3: Output count
            num_outputs = len(outputs)
            condition3 = n_estimated >= (num_outputs - 1) / 2
            
            # Mathematical Condition 4: Unique output scripts
            condition4 = num_outputs == nscripts_out
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Denomination condition met: {d_hat/10**8:.8f} BTC ≈ 0.1 BTC")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"Input constraints met: {n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated}")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Output count condition met: {n_estimated} >= ({num_outputs}-1)/2")
            
            if condition4:
                confidence += 0.1
                reasons.append(f"Unique scripts condition met: {num_outputs} == {nscripts_out}")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': n_estimated,
                'denomination': d_hat,
                'conditions_met': [condition1, condition2, condition3, condition4],
                'mathematical_analysis': {
                    'n_estimated': n_estimated,
                    'd_hat': d_hat,
                    'target_denomination': target_denomination_satoshis,
                    'epsilon': epsilon_satoshis,
                    'condition_checks': {
                        '1_denomination': f"{target_denomination_satoshis - epsilon_satoshis} <= {d_hat} <= {target_denomination_satoshis + epsilon_satoshis} = {condition1}",
                        '2_input_constraints': f"{n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated} = {condition2}",
                        '3_output_count': f"{n_estimated} >= ({num_outputs}-1)/2 = {condition3}",
                        '4_unique_scripts': f"{num_outputs} == {nscripts_out} = {condition4}"
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Wasabi 1.0 detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def detect_wasabi_1_1(self, analysis_data: Dict) -> Dict:
        """
        Enhanced Wasabi 1.1 detection with L parameter
        
        Mathematical Conditions:
        1. Post-mix denomination: 0.1 - ε <= d_hat <= 0.1 + ε BTC
        2. Input/output constraints: n_estimated <= nscripts_in <= |∆in| <= amax * n_estimated  
        3. Output count: n_estimated >= (|∆out| - 1) / 2
        4. Unique output scripts: |∆out| = nscripts_out
        5. L parameter: n_estimated <= max_mixing_level
        """
        try:
            config = self.config['wasabi_1_1']
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            nscripts_in = analysis_data['nscripts_in']
            nscripts_out = analysis_data['nscripts_out']
            
            # Convert parameters to satoshis
            target_denomination_satoshis = int(config['target_denomination_btc'] * 10**8)
            epsilon_satoshis = int(config['epsilon_btc'] * 10**8)
            amax = config['amax']
            max_mixing_level = config['max_mixing_level']
            
            # Estimate n and d
            value_counts = {}
            for val in outputs:
                value_counts[val] = value_counts.get(val, 0) + 1
            
            if not value_counts:
                return {'confidence': 0.0, 'error': 'No output values found'}
            
            n_estimated = max(value_counts.values())
            
            # Find possible denominations (values with max count)
            d_possible_denominations = {val for val, count in value_counts.items() if count == n_estimated}
            
            # Find d_hat (closest to 0.1 BTC)
            d_hat = min(d_possible_denominations, 
                       key=lambda x: abs(x - target_denomination_satoshis))
            
            # Mathematical Condition 1: Denomination near 0.1 BTC
            condition1 = (target_denomination_satoshis - epsilon_satoshis <= d_hat <= 
                         target_denomination_satoshis + epsilon_satoshis)
            
            # Mathematical Condition 2: Input/output constraints
            num_inputs = len(inputs)
            condition2 = (n_estimated <= nscripts_in and 
                         nscripts_in <= num_inputs and 
                         num_inputs <= amax * n_estimated)
            
            # Mathematical Condition 3: Output count
            num_outputs = len(outputs)
            condition3 = n_estimated >= (num_outputs - 1) / 2
            
            # Mathematical Condition 4: Unique output scripts
            condition4 = num_outputs == nscripts_out
            
            # Mathematical Condition 5: L parameter
            condition5 = n_estimated <= max_mixing_level
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Denomination condition met: {d_hat/10**8:.8f} BTC ≈ 0.1 BTC")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"Input constraints met: {n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated}")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Output count condition met: {n_estimated} >= ({num_outputs}-1)/2")
            
            if condition4:
                confidence += 0.1
                reasons.append(f"Unique scripts condition met: {num_outputs} == {nscripts_out}")
            
            if condition5:
                confidence += 0.1
                reasons.append(f"L parameter condition met: {n_estimated} <= {max_mixing_level}")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': n_estimated,
                'denomination': d_hat,
                'conditions_met': [condition1, condition2, condition3, condition4, condition5],
                'mathematical_analysis': {
                    'n_estimated': n_estimated,
                    'd_hat': d_hat,
                    'target_denomination': target_denomination_satoshis,
                    'epsilon': epsilon_satoshis,
                    'condition_checks': {
                        '1_denomination': f"{target_denomination_satoshis - epsilon_satoshis} <= {d_hat} <= {target_denomination_satoshis + epsilon_satoshis} = {condition1}",
                        '2_input_constraints': f"{n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated} = {condition2}",
                        '3_output_count': f"{n_estimated} >= ({num_outputs}-1)/2 = {condition3}",
                        '4_unique_scripts': f"{num_outputs} == {nscripts_out} = {condition4}",
                        '5_l_parameter': f"{n_estimated} <= {max_mixing_level} = {condition5}"
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Wasabi 1.1 detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def detect_wasabi_2_0(self, analysis_data: Dict) -> Dict:
        """
        Enhanced Wasabi 2.0 detection with fixed denominations
        
        Mathematical Conditions:
        1. Post-mix denomination: d_hat in denominations_satoshis
        2. Input/output constraints: n_estimated <= nscripts_in <= |∆in| <= amax * n_estimated  
        3. Output count: n_estimated >= (|∆out| - 1) / 2
        4. Unique output scripts: |∆out| = nscripts_out
        5. vmin condition: d_hat >= vmin
        """
        try:
            config = self.config['wasabi_2_0']
            outputs = analysis_data['output_amounts']
            inputs = analysis_data['input_amounts']
            nscripts_in = analysis_data['nscripts_in']
            nscripts_out = analysis_data['nscripts_out']
            
            # Convert parameters to satoshis
            denominations_satoshis = config['denominations_satoshis']
            amax = config['amax']
            vmin = config['vmin']
            
            # Estimate n and d
            value_counts = {}
            for val in outputs:
                value_counts[val] = value_counts.get(val, 0) + 1
            
            if not value_counts:
                return {'confidence': 0.0, 'error': 'No output values found'}
            
            n_estimated = max(value_counts.values())
            
            # Find possible denominations (values with max count)
            d_possible_denominations = {val for val, count in value_counts.items() if count == n_estimated}
            
            # Find d_hat (closest to a fixed denomination)
            d_hat = min(d_possible_denominations, 
                       key=lambda x: min(abs(x - d) for d in denominations_satoshis))
            
            # Mathematical Condition 1: Denomination in fixed list
            condition1 = d_hat in denominations_satoshis
            
            # Mathematical Condition 2: Input/output constraints
            num_inputs = len(inputs)
            condition2 = (n_estimated <= nscripts_in and 
                         nscripts_in <= num_inputs and 
                         num_inputs <= amax * n_estimated)
            
            # Mathematical Condition 3: Output count
            num_outputs = len(outputs)
            condition3 = n_estimated >= (num_outputs - 1) / 2
            
            # Mathematical Condition 4: Unique output scripts
            condition4 = num_outputs == nscripts_out
            
            # Mathematical Condition 5: vmin condition
            condition5 = d_hat >= vmin
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Denomination condition met: {d_hat/10**8:.8f} BTC is in fixed list")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"Input constraints met: {n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated}")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Output count condition met: {n_estimated} >= ({num_outputs}-1)/2")
            
            if condition4:
                confidence += 0.1
                reasons.append(f"Unique scripts condition met: {num_outputs} == {nscripts_out}")
            
            if condition5:
                confidence += 0.1
                reasons.append(f"vmin condition met: {d_hat} >= {vmin}")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': n_estimated,
                'denomination': d_hat,
                'conditions_met': [condition1, condition2, condition3, condition4, condition5],
                'mathematical_analysis': {
                    'n_estimated': n_estimated,
                    'd_hat': d_hat,
                    'denominations': denominations_satoshis,
                    'amax': amax,
                    'vmin': vmin,
                    'condition_checks': {
                        '1_denomination': f"{d_hat} in {denominations_satoshis} = {condition1}",
                        '2_input_constraints': f"{n_estimated} <= {nscripts_in} <= {num_inputs} <= {amax * n_estimated} = {condition2}",
                        '3_output_count': f"{n_estimated} >= ({num_outputs}-1)/2 = {condition3}",
                        '4_unique_scripts': f"{num_outputs} == {nscripts_out} = {condition4}",
                        '5_vmin': f"{d_hat} >= {vmin} = {condition5}"
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Wasabi 2.0 detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}
    
    def detect_whirlpool_tx0(self, analysis_data: Dict) -> Dict:
        """
        Detect Whirlpool Tx0 (pre-mix) transactions
        
        Mathematical Conditions:
        1. Pre-mix output count: Count of d_tilde outputs >= |∆out| - 3
        2. Required outputs: >=1 pre-mix, exactly 1 coordinator fee, exactly 1 zero-value
        3. Maximum pre-mix outputs: Count <= amax
        4. Valid epsilon: εmin <= ε_tilde <= εmax
        """
        try:
            config = self.config['whirlpool_tx0']
            pools = self.config['whirlpool_pools']
            outputs = analysis_data['output_amounts']
            
            amax = config['amax']
            eta1 = config['eta1']
            eta2 = config['eta2']
            epsilon_min = config['epsilon_min']
            epsilon_max = config['epsilon_max']
            
            pools_satoshis = [(int(d * 10**8), int(f * 10**8)) for d, f in pools]
            num_outputs = len(outputs)
            
            # Find candidate pre-mix values
            candidate_pre_mix_values = []
            for val in outputs:
                for d_pool_satoshis, _ in pools_satoshis:
                    if d_pool_satoshis + epsilon_min <= val <= d_pool_satoshis + epsilon_max:
                        candidate_pre_mix_values.append(val)
                        break
            
            if not candidate_pre_mix_values:
                return {'confidence': 0.0, 'reason': 'No candidate pre-mix values found'}
            
            # Find d_tilde (most frequent candidate, highest on tie)
            val_counts = {}
            for val in candidate_pre_mix_values:
                val_counts[val] = val_counts.get(val, 0) + 1
            
            d_tilde = max(val_counts.items(), key=lambda x: (x[1], x[0]))[0]
            
            # Find matching pool
            d_hat = None
            f_hat = None
            min_diff = float('inf')
            for d_pool_satoshis, f_pool_satoshis in pools_satoshis:
                if d_pool_satoshis <= d_tilde:
                    diff = abs(d_pool_satoshis - d_tilde)
                    if diff < min_diff:
                        min_diff = diff
                        d_hat = d_pool_satoshis
                        f_hat = f_pool_satoshis
            
            if d_hat is None or f_hat is None:
                return {'confidence': 0.0, 'reason': 'No matching pool found'}
            
            epsilon_tilde = d_tilde - d_hat
            
            # Count outputs
            count_pre_mix_outputs = outputs.count(d_tilde)
            count_coordinator_fee_outputs = sum(1 for val in outputs if eta1 * f_hat <= val <= eta2 * f_hat)
            count_zero_value_outputs = outputs.count(0)
            
            # Mathematical Conditions
            condition1 = count_pre_mix_outputs >= num_outputs - 3
            condition2 = (count_pre_mix_outputs >= 1 and 
                         count_coordinator_fee_outputs == 1 and 
                         count_zero_value_outputs == 1)
            condition3 = count_pre_mix_outputs <= amax
            condition4 = epsilon_min <= epsilon_tilde <= epsilon_max
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.4
                reasons.append(f"Pre-mix count condition met: {count_pre_mix_outputs} >= {num_outputs - 3}")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"Required outputs met: {count_pre_mix_outputs} pre-mix, {count_coordinator_fee_outputs} coordinator fee, {count_zero_value_outputs} zero-value")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Max pre-mix condition met: {count_pre_mix_outputs} <= {amax}")
            
            if condition4:
                confidence += 0.1
                reasons.append(f"Epsilon condition met: {epsilon_min} <= {epsilon_tilde} <= {epsilon_max}")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': count_pre_mix_outputs,
                'denomination': d_hat,
                'conditions_met': [condition1, condition2, condition3, condition4],
                'mathematical_analysis': {
                    'd_tilde': d_tilde,
                    'd_hat': d_hat,
                    'f_hat': f_hat,
                    'epsilon_tilde': epsilon_tilde,
                    'pre_mix_count': count_pre_mix_outputs,
                    'coordinator_fee_count': count_coordinator_fee_outputs,
                    'zero_value_count': count_zero_value_outputs
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Whirlpool Tx0 detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}

    def detect_whirlpool_mix(self, analysis_data: Dict) -> Dict:
        """
        Detect Whirlpool CoinJoin (Mix) transactions
        
        Mathematical Conditions:
        1. Fixed structure: Exactly 5 inputs, 5 outputs, all scripts unique
        2. Standard outputs/inputs: All 5 outputs have pool denomination d, all 5 inputs in range [d, d + εmax]
        3. Mix input requirement: 1-4 inputs from previous mixes (v > d)
        """
        try:
            config = self.config['whirlpool_mix']
            pools = self.config['whirlpool_pools']
            
            input_amounts = analysis_data['input_amounts']
            output_amounts = analysis_data['output_amounts']
            input_scripts = analysis_data['input_scripts']
            output_scripts = analysis_data['output_scripts']
            
            epsilon_max = config['epsilon_max']
            pools_satoshis = [(int(d * 10**8), int(f * 10**8)) for d, f in pools]
            
            # Mathematical Condition 1: Fixed structure
            condition1 = (len(input_amounts) == 5 and 
                         len(set(input_scripts)) == 5 and 
                         len(set(output_scripts)) == 5 and 
                         len(output_amounts) == 5)
            
            if not condition1:
                return {'confidence': 0.0, 'reason': '5x5 structure not met'}
            
            # Find matching pool for 5 equal outputs
            d_pool_matched = None
            for d_pool_satoshis, _ in pools_satoshis:
                if output_amounts.count(d_pool_satoshis) == 5:
                    d_pool_matched = d_pool_satoshis
                    break
            
            if d_pool_matched is None:
                return {'confidence': 0.0, 'reason': 'No matching pool denomination found'}
            
            # Mathematical Condition 2: Valid inputs
            count_valid_inputs = sum(1 for val in input_amounts 
                                   if d_pool_matched <= val <= d_pool_matched + epsilon_max)
            condition2 = count_valid_inputs == 5
            
            # Mathematical Condition 3: Mix input requirement
            count_inputs_gt_d = sum(1 for val in input_amounts if val > d_pool_matched)
            condition3 = 1 <= count_inputs_gt_d <= 4
            
            confidence = 0.0
            reasons = []
            
            if condition1:
                confidence += 0.5
                reasons.append("Classic 5x5 Whirlpool structure confirmed")
            
            if condition2:
                confidence += 0.3
                reasons.append(f"All inputs valid: 5 inputs in range [{d_pool_matched}, {d_pool_matched + epsilon_max}]")
            
            if condition3:
                confidence += 0.2
                reasons.append(f"Mix input requirement met: {count_inputs_gt_d} inputs > denomination")
            
            return {
                'confidence': min(confidence, 1.0),
                'reasons': reasons,
                'participants': 5,  # Always 5 in Whirlpool mix
                'denomination': d_pool_matched,
                'conditions_met': [condition1, condition2, condition3],
                'mathematical_analysis': {
                    'd_pool_matched': d_pool_matched,
                    'valid_inputs_count': count_valid_inputs,
                    'inputs_gt_d_count': count_inputs_gt_d,
                    'epsilon_max': epsilon_max
                }
            }
            
        except Exception as e:
            logger.error(f"Error in Whirlpool Mix detection: {e}")
            return {'confidence': 0.0, 'error': str(e)}

    # Legacy methods for backward compatibility (deprecated)
    def detect_joinmarket(self, analysis_data: Dict) -> Dict:
        """Legacy JoinMarket detection - redirects to enhanced version"""
        return self.detect_joinmarket_v2(analysis_data)
    
    def detect_wasabi_v1(self, analysis_data: Dict) -> Dict:
        """Legacy Wasabi detection - redirects to enhanced version"""
        return self.detect_wasabi_1_0(analysis_data)
    
    def detect_whirlpool(self, analysis_data: Dict) -> Dict:
        """Legacy Whirlpool detection - tries both Tx0 and Mix"""
        tx0_result = self.detect_whirlpool_tx0(analysis_data)
        mix_result = self.detect_whirlpool_mix(analysis_data)
        
        # Return the result with higher confidence
        if tx0_result['confidence'] > mix_result['confidence']:
            return tx0_result
        else:
            return mix_result
    
    def _group_similar_amounts(self, amounts: List[int], tolerance: int) -> List[List[int]]:
        """Group amounts that are within tolerance of each other"""
        if not amounts:
            return []
        
        groups = []
        remaining = amounts.copy()
        
        while remaining:
            current = remaining.pop(0)
            group = [current]
            
            # Find all amounts within tolerance
            to_remove = []
            for i, amount in enumerate(remaining):
                if abs(amount - current) <= tolerance:
                    group.append(amount)
                    to_remove.append(i)
            
            # Remove grouped amounts (in reverse order to maintain indices)
            for i in reversed(to_remove):
                remaining.pop(i)
            
            if len(group) > 1:  # Only include groups with multiple items
                groups.append(group)
        
        return groups
    
    def _negative_result(self, reason: str, analysis_data: Dict = None) -> Dict:
        """Return a negative detection result"""
        result = {
            'is_coinjoin': False,
            'coinjoin_type': None,
            'confidence': 0.0,
            'analysis': {'reason': reason}
        }
        
        if analysis_data:
            result['analysis']['transaction_structure'] = analysis_data
        
        return result 