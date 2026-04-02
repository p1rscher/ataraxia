# cogs/math.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
import sympy as sp
from sympy import symbols, solve, Matrix, sympify, I, sqrt, pi, E, root
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application
import re
import asyncio

logger = logging.getLogger(__name__)

class MathCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    math_group = app_commands.Group(name="math", description="Mathematical operations")

    @math_group.command(name="help")
    async def math_help(self, interaction: discord.Interaction):
        """Show all available math operations and functions"""
        embed = discord.Embed(
            title="📚 Math Module Help",
            description="Complete guide to mathematical operations",
            color=discord.Color.blue()
        )
        
        # Basic Operations
        embed.add_field(
            name="➕ Basic Operations",
            value=(
                "`+` Addition\n"
                "`-` Subtraction\n"
                "`*` Multiplication\n"
                "`/` Division\n"
                "`^` or `**` Power/Exponentiation\n"
                "`%` Modulo"
            ),
            inline=True
        )
        
        # Functions
        embed.add_field(
            name="🔢 Functions",
            value=(
                "`sqrt(x)` Square root\n"
                "`root(x, n)` n-th root\n"
                "`abs(x)` Absolute value\n"
                "`exp(x)` Exponential (e^x)\n"
                "`log(x)` or `log(x,base)` Logarithm\n"
                "`ln(x)` Natural logarithm\n"
                "`factorial(n)` Factorial (n!)"
            ),
            inline=True
        )
        
        # Trigonometric
        embed.add_field(
            name="📐 Trigonometric",
            value=(
                "`sin(x)` Sine\n"
                "`cos(x)` Cosine\n"
                "`tan(x)` Tangent\n"
                "`asin(x)` Arcsine\n"
                "`acos(x)` Arccosine\n"
                "`atan(x)` Arctangent"
            ),
            inline=True
        )
        
        # Hyperbolic
        embed.add_field(
            name="〰️ Hyperbolic",
            value=(
                "`sinh(x)` Hyperbolic sine\n"
                "`cosh(x)` Hyperbolic cosine\n"
                "`tanh(x)` Hyperbolic tangent"
            ),
            inline=True
        )
        
        # Constants
        embed.add_field(
            name="🔤 Constants",
            value=(
                "`pi` or `π` Pi (3.14159...)\n"
                "`e` or `E` Euler's number (2.71828...)\n"
                "`i` or `I` Imaginary unit (√-1)\n"
                "`oo` Infinity"
            ),
            inline=True
        )
        
        # Examples
        embed.add_field(
            name="💡 Examples",
            value=(
                "`/math calc sqrt(16) + 2^3`\n"
                "`/math calc root(27, 3)`\n"
                "`/math calc sin(pi/2)`\n"
                "`/math calc e^(I*pi) + 1`\n"
                "`/math solve x^2 + 1 = 0`\n"
                "`/math solve_system 2x+y=5; x-y=1`"
            ),
            inline=False
        )
        
        # Matrix Format
        embed.add_field(
            name="🔲 Matrix Format",
            value=(
                "Rows separated by `;`, elements by `,`\n"
                "**Example:** `1,2;3,4` = [[1,2], [3,4]]\n"
                "`/math matrix multiply 1,2;3,4 and 5,6;7,8`"
            ),
            inline=False
        )
        
        embed.set_footer(text="Complex numbers and symbolic computation supported!")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @math_group.command(name="calc")
    @app_commands.describe(expression="Mathematical expression to calculate")
    async def calculate(self, interaction: discord.Interaction, expression: str):
        """Calculate a mathematical expression"""
        # Check for exponent limit
        if not self._check_exponent_limit(expression):
            await interaction.response.send_message(
                "❌ Expression contains exponents that are too large (max: 50,000).\n"
                "This is to prevent server overload.",
                ephemeral=True
            )
            return
        
        # Defer for potentially long calculations
        await interaction.response.defer()
        
        try:
            # Replace ^ with ** for power
            expression_parsed = expression.replace('^', '**')
            
            # Parse and evaluate the expression with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            
            # Define local dict with constants and functions
            local_dict = {
                'e': E,
                'E': E,
                'i': I,
                'I': I,
                'pi': pi,
                'π': pi,
                'root': root,
                'sqrt': sqrt
            }
            
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(parse_expr, expression_parsed, transformations=transformations, local_dict=local_dict),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "⏱️ Calculation timed out (>10 seconds). Expression too complex.",
                    ephemeral=True
                )
                return
            
            # Simplify the expression first
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(sp.simplify, result),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                pass  # Keep unsimplified result if timeout
            
            # Get symbolic representation
            symbolic_str = str(result).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            numerical_str = None
            
            # Evaluate numerically if possible
            if result.is_number:
                # For very large integer results, don't use evalf (it's slow)
                if result.is_Integer and abs(result) > 10**100:
                    # Just use the symbolic result for huge integers
                    result_str = symbolic_str
                else:
                    try:
                        # Timeout for numerical evaluation
                        numerical_result = await asyncio.wait_for(
                            asyncio.to_thread(lambda: complex(result.evalf())),
                            timeout=5.0
                        )
                        if numerical_result.imag == 0:
                            numerical_str = f"{numerical_result.real:g}"
                        else:
                            numerical_str = f"{numerical_result.real:g} + {numerical_result.imag:g}i"
                        result_str = numerical_str
                    except asyncio.TimeoutError:
                        # Fallback to symbolic representation
                        result_str = symbolic_str
            else:
                result_str = symbolic_str
            
            # Check if result is a very large number
            if result.is_Integer:
                result_str_full = str(result)
                num_digits = len(result_str_full)
                
                # If result has more than 1000 digits, show compact format
                if num_digits > 1000:
                    embed = discord.Embed(
                        title="🧮 Calculator",
                        color=discord.Color.blue()
                    )
                    embed.add_field(name="Expression", value=f"`{expression.replace('**', '^')}`", inline=False)
                    embed.add_field(
                        name="Result",
                        value=f"**Number has {num_digits:,} digits**\n\n"
                              f"First 100 digits:\n`{result_str_full[:100]}`\n\n"
                              f"Last 100 digits:\n`...{result_str_full[-100:]}`",
                        inline=False
                    )
                    await interaction.followup.send(embed=embed)
                    return
            
            # Check if result string is too long (> 2000 chars for Discord embed limit)
            if len(result_str) > 1900:
                embed = discord.Embed(
                    title="🧮 Calculator",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Expression", value=f"`{expression.replace('**', '^')}`", inline=False)
                embed.add_field(
                    name="Result",
                    value=f"Result is too large to display fully.\n\n"
                          f"First 100 characters:\n`{result_str[:100]}`\n\n"
                          f"Last 100 characters:\n`...{result_str[-100:]}`",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="🧮 Calculator",
                color=discord.Color.blue()
            )
            embed.add_field(name="Expression", value=f"`{expression.replace('**', '^')}`", inline=False)
            
            # Show both symbolic and numerical if they differ
            if numerical_str and symbolic_str != numerical_str:
                embed.add_field(name="Symbolic", value=f"`{symbolic_str}`", inline=False)
                embed.add_field(name="Numerical", value=f"`{numerical_str}`", inline=False)
            else:
                embed.add_field(name="Result", value=f"`{result_str}`", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in calc command: {e}")
            
            # Check if it's a "result too large" type error
            if "exceeds" in error_msg.lower() or "limit" in error_msg.lower() or "too large" in error_msg.lower():
                await interaction.followup.send(
                    "❌ **Result is too large to compute.**\n\n"
                    "The calculation would produce a number that's too big to handle.\n"
                    "Try reducing the exponent or using smaller numbers.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Error parsing expression: {error_msg}\n\n"
                    f"**Supported operations:**\n"
                    f"• Basic: `+, -, *, /, ^` or `**` for power\n"
                    f"• Functions: `sqrt(), sin(), cos(), tan(), log(), ln(), exp()`\n"
                    f"• Constants: `pi, e, I` (imaginary unit)\n"
                    f"• Example: `sqrt(16) + 2^3` or `sin(pi/2)`",
                    ephemeral=True
                )

    @math_group.command(name="solve")
    @app_commands.describe(equation="Equation to solve (e.g., x^2 + 5x + 6 = 0)")
    async def solve_equation(self, interaction: discord.Interaction, equation: str):
        """Solve an equation (supports complex solutions)"""
        try:
            # Replace ^ with ** for power
            equation = equation.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            
            # Split equation by '='
            if '=' in equation:
                left, right = equation.split('=', 1)
                expr = parse_expr(left, transformations=transformations) - parse_expr(right, transformations=transformations)
            else:
                expr = parse_expr(equation, transformations=transformations)
            
            # Find all variables
            variables = list(expr.free_symbols)
            
            if not variables:
                await interaction.response.send_message("❌ No variables found in the equation.", ephemeral=True)
                return
            
            if len(variables) > 1:
                await interaction.response.send_message(
                    f"❌ Multiple variables found: {', '.join(str(v) for v in variables)}\n"
                    f"Please use `/solve_system` for systems of equations.",
                    ephemeral=True
                )
                return
            
            # Solve the equation
            solutions = solve(expr, variables[0])
            
            if not solutions:
                await interaction.response.send_message("❌ No solution found.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🔍 Equation Solver",
                color=discord.Color.green()
            )
            # Replace symbols in equation display
            equation_display = equation.replace('**', '^')
            embed.add_field(name="Equation", value=f"`{equation_display}`", inline=False)
            
            # Format solutions
            solutions_text = ""
            for i, sol in enumerate(solutions, 1):
                # Check if solution is complex
                sol_eval = complex(sol.evalf())
                if sol_eval.imag != 0:
                    if sol_eval.real == 0:
                        solutions_text += f"**{variables[0]}** = `{sol_eval.imag:g}i`\n"
                    else:
                        solutions_text += f"**{variables[0]}** = `{sol_eval.real:g} + {sol_eval.imag:g}i`\n"
                else:
                    solutions_text += f"**{variables[0]}** = `{sol_eval.real:g}`\n"
            
            embed.add_field(name=f"Solution{'s' if len(solutions) > 1 else ''}", value=solutions_text, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in solve command: {e}")
            await interaction.response.send_message(
                f"❌ Error solving equation: {str(e)}\n\n"
                f"**Example:** `x^2 + 1 = 0` or `2x + 5 = 11`",
                ephemeral=True
            )

    @math_group.command(name="solve_system")
    @app_commands.describe(
        equations="Equations separated by semicolons (e.g., 2x + y = 5; x - y = 1)"
    )
    async def solve_system(self, interaction: discord.Interaction, equations: str):
        """Solve a system of equations (supports complex solutions)"""
        try:
            # Replace ^ with ** for power
            equations = equations.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            
            # Split equations by semicolon
            eq_list = [eq.strip() for eq in equations.split(';') if eq.strip()]
            
            if len(eq_list) < 2:
                await interaction.response.send_message(
                    "❌ Please provide at least 2 equations separated by semicolons.\n"
                    "**Example:** `2x + y = 5; x - y = 1`",
                    ephemeral=True
                )
                return
            
            # Parse equations
            expr_list = []
            all_variables = set()
            
            for eq in eq_list:
                if '=' in eq:
                    left, right = eq.split('=', 1)
                    expr = parse_expr(left, transformations=transformations) - parse_expr(right, transformations=transformations)
                else:
                    expr = parse_expr(eq, transformations=transformations)
                
                expr_list.append(expr)
                all_variables.update(expr.free_symbols)
            
            if not all_variables:
                await interaction.response.send_message("❌ No variables found in the equations.", ephemeral=True)
                return
            
            # Solve the system
            variables = sorted(all_variables, key=str)
            solutions = solve(expr_list, variables)
            
            if not solutions:
                await interaction.response.send_message("❌ No solution found for this system.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🔢 System of Equations Solver",
                color=discord.Color.purple()
            )
            
            # Display equations
            equations_text = "\n".join(f"`{eq}`" for eq in eq_list)
            embed.add_field(name="Equations", value=equations_text, inline=False)
            
            # Format solutions
            solutions_text = ""
            
            # Handle different solution formats
            if isinstance(solutions, dict):
                for var, sol in solutions.items():
                    sol_eval = complex(sol.evalf())
                    if sol_eval.imag != 0:
                        if sol_eval.real == 0:
                            solutions_text += f"**{var}** = `{sol_eval.imag:g}i`\n"
                        else:
                            solutions_text += f"**{var}** = `{sol_eval.real:g} + {sol_eval.imag:g}i`\n"
                    else:
                        solutions_text += f"**{var}** = `{sol_eval.real:g}`\n"
            elif isinstance(solutions, list):
                for i, sol_set in enumerate(solutions, 1):
                    if len(solutions) > 1:
                        solutions_text += f"**Solution {i}:**\n"
                    if isinstance(sol_set, dict):
                        for var, sol in sol_set.items():
                            sol_eval = complex(sol.evalf())
                            if sol_eval.imag != 0:
                                solutions_text += f"**{var}** = `{sol_eval.real:g} + {sol_eval.imag:g}i`\n"
                            else:
                                solutions_text += f"**{var}** = `{sol_eval.real:g}`\n"
                    else:
                        for var, sol in zip(variables, sol_set):
                            sol_eval = complex(sol.evalf())
                            if sol_eval.imag != 0:
                                solutions_text += f"**{var}** = `{sol_eval.real:g} + {sol_eval.imag:g}i`\n"
                            else:
                                solutions_text += f"**{var}** = `{sol_eval.real:g}`\n"
            
            embed.add_field(name="Solutions", value=solutions_text or "No solution", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in solve_system command: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ Error solving system: {str(e)}\n\n"
                f"**Example:** `2x + y = 5; x - y = 1`",
                ephemeral=True
            )

    @math_group.command(name="derivative")
    @app_commands.describe(
        function="Function to differentiate (e.g., x^2 + 3x)",
        variable="Variable to differentiate with respect to (default: x)"
    )
    async def derivative(self, interaction: discord.Interaction, function: str, variable: str = "x"):
        """Calculate the derivative of a function"""
        try:
            # Replace ^ with ** for power
            function = function.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            expr = parse_expr(function, transformations=transformations)
            var = symbols(variable)
            
            # Calculate derivative
            derivative = sp.diff(expr, var)
            
            embed = discord.Embed(
                title="📐 Derivative",
                color=discord.Color.blue()
            )
            # Format output with lowercase symbols
            derivative_str = str(derivative).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            
            embed.add_field(name="Function", value=f"`f({variable}) = {function.replace('**', '^')}`", inline=False)
            embed.add_field(name="Derivative", value=f"`f'({variable}) = {derivative_str}`", inline=False)
            
            # Try to simplify
            simplified = sp.simplify(derivative)
            if str(simplified) != str(derivative):
                simplified_str = str(simplified).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                embed.add_field(name="Simplified", value=f"`{simplified_str}`", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in derivative command: {e}")
            await interaction.response.send_message(
                f"❌ Error calculating derivative: {str(e)}\n\n"
                f"**Example:** `/math derivative x^3 + 2x^2 + x`",
                ephemeral=True
            )

    @math_group.command(name="integrate")
    @app_commands.describe(
        function="Function to integrate (e.g., x^2 + 3x)",
        variable="Variable to integrate with respect to (default: x)",
        definite="Definite integral bounds (format: a,b e.g., 0,5)"
    )
    async def integrate(self, interaction: discord.Interaction, function: str, variable: str = "x", definite: str = None):
        """Calculate the integral of a function"""
        try:
            # Replace ^ with ** for power
            function = function.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            expr = parse_expr(function, transformations=transformations)
            var = symbols(variable)
            
            embed = discord.Embed(
                title="∫ Integration",
                color=discord.Color.green()
            )
            
            if definite:
                # Definite integral
                try:
                    bounds = definite.split(',')
                    if len(bounds) != 2:
                        raise ValueError("Bounds must be in format: a,b")
                    
                    a = parse_expr(bounds[0].strip(), transformations=transformations)
                    b = parse_expr(bounds[1].strip(), transformations=transformations)
                    
                    result = sp.integrate(expr, (var, a, b))
                    result_str = str(result).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                    a_str = str(a).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                    b_str = str(b).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                    
                    embed.add_field(name="Function", value=f"`f({variable}) = {function.replace('**', '^')}`", inline=False)
                    embed.add_field(name="Bounds", value=f"`[{a_str}, {b_str}]`", inline=False)
                    embed.add_field(name="Definite Integral", value=f"`∫[{a_str} to {b_str}] f({variable}) d{variable} = {result_str}`", inline=False)
                    
                    # Try to evaluate numerically
                    try:
                        numerical = complex(result.evalf())
                        if numerical.imag == 0:
                            embed.add_field(name="Numerical Value", value=f"`≈ {numerical.real:g}`", inline=False)
                        else:
                            embed.add_field(name="Numerical Value", value=f"`≈ {numerical.real:g} + {numerical.imag:g}i`", inline=False)
                    except:
                        pass
                    
                except Exception as e:
                    await interaction.response.send_message(
                        f"❌ Error with definite integral: {str(e)}\n"
                        f"Bounds format: `a,b` (e.g., `0,5`)",
                        ephemeral=True
                    )
                    return
            else:
                # Indefinite integral
                integral = sp.integrate(expr, var)
                integral_str = str(integral).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                
                embed.add_field(name="Function", value=f"`f({variable}) = {function.replace('**', '^')}`", inline=False)
                embed.add_field(name="Indefinite Integral", value=f"`∫ f({variable}) d{variable} = {integral_str} + C`", inline=False)
                
                # Try to simplify
                simplified = sp.simplify(integral)
                if str(simplified) != str(integral):
                    simplified_str = str(simplified).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
                    embed.add_field(name="Simplified", value=f"`{simplified_str} + C`", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in integrate command: {e}")
            await interaction.response.send_message(
                f"❌ Error calculating integral: {str(e)}\n\n"
                f"**Examples:**\n"
                f"• Indefinite: `/math integrate x^2 + 3x`\n"
                f"• Definite: `/math integrate x^2 definite:0,5`",
                ephemeral=True
            )

    @math_group.command(name="sum")
    @app_commands.describe(
        expression="Expression to sum (e.g., n^2 or 1/n)",
        variable="Summation variable (default: n)",
        start="Start value (e.g., 1)",
        end="End value (e.g., 10 or oo for infinity)"
    )
    async def sum_formula(self, interaction: discord.Interaction, expression: str, variable: str = "n", start: str = "1", end: str = "10"):
        """Calculate a sum (Σ notation)"""
        await interaction.response.defer()
        
        try:
            # Replace ^ with ** for power
            expression = expression.replace('^', '**')
            start = start.replace('^', '**')
            end = end.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            expr = parse_expr(expression, transformations=transformations)
            var = symbols(variable)
            
            # Parse bounds
            if start.lower() in ['oo', 'inf', 'infinity']:
                start_val = sp.oo
            elif start.lower() in ['-oo', '-inf', '-infinity']:
                start_val = -sp.oo
            else:
                start_val = parse_expr(start, transformations=transformations)
            
            if end.lower() in ['oo', 'inf', 'infinity']:
                end_val = sp.oo
            elif end.lower() in ['-oo', '-inf', '-infinity']:
                end_val = -sp.oo
            else:
                end_val = parse_expr(end, transformations=transformations)
            
            # Calculate sum
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(sp.summation, expr, (var, start_val, end_val)),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    "⏱️ Sum calculation timed out (>10 seconds). Series too complex.",
                    ephemeral=True
                )
                return
            
            result_str = str(result).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            start_str = str(start_val).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            end_str = str(end_val).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            
            embed = discord.Embed(
                title="Σ Sum",
                color=discord.Color.orange()
            )
            embed.add_field(name="Expression", value=f"`Σ({variable}={start_str} to {end_str}) {expression.replace('**', '^')}`", inline=False)
            embed.add_field(name="Result", value=f"`{result_str}`", inline=False)
            
            # Try to evaluate numerically if possible
            if result.is_number:
                try:
                    numerical = complex(result.evalf())
                    if numerical.imag == 0:
                        embed.add_field(name="Numerical Value", value=f"`≈ {numerical.real:g}`", inline=False)
                    else:
                        embed.add_field(name="Numerical Value", value=f"`≈ {numerical.real:g} + {numerical.imag:g}i`", inline=False)
                except:
                    pass
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in sum command: {e}")
            await interaction.followup.send(
                f"❌ Error calculating sum: {str(e)}\n\n"
                f"**Examples:**\n"
                f"• `/math sum n^2 start:1 end:10`\n"
                f"• `/math sum 1/n start:1 end:oo` (infinite series)\n"
                f"• `/math sum 2^n variable:n start:0 end:5`",
                ephemeral=True
            )

    @math_group.command(name="limit")
    @app_commands.describe(
        function="Function to find the limit of (e.g., sin(x)/x)",
        variable="Variable (default: x)",
        point="Point to approach (e.g., 0, oo for infinity)",
        direction="Direction ('+' from right, '-' from left, default: both)"
    )
    async def limit(self, interaction: discord.Interaction, function: str, variable: str = "x", point: str = "0", direction: str = None):
        """Calculate the limit of a function"""
        try:
            # Replace ^ with ** for power
            function = function.replace('^', '**')
            point = point.replace('^', '**')
            
            # Parse with implicit multiplication
            transformations = standard_transformations + (implicit_multiplication_application,)
            expr = parse_expr(function, transformations=transformations)
            var = symbols(variable)
            
            # Parse point (handle 'oo' for infinity)
            if point.lower() in ['oo', 'inf', 'infinity']:
                limit_point = sp.oo
            elif point.lower() in ['-oo', '-inf', '-infinity']:
                limit_point = -sp.oo
            else:
                limit_point = parse_expr(point, transformations=transformations)
            
            # Calculate limit
            if direction == '+':
                result = sp.limit(expr, var, limit_point, '+')
                dir_text = "from the right"
            elif direction == '-':
                result = sp.limit(expr, var, limit_point, '-')
                dir_text = "from the left"
            else:
                result = sp.limit(expr, var, limit_point)
                dir_text = ""
            
            result_str = str(result).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            limit_point_str = str(limit_point).replace('**', '^').replace('E', 'e').replace('I', 'i').replace('pi', 'π')
            
            embed = discord.Embed(
                title="📊 Limit",
                color=discord.Color.purple()
            )
            embed.add_field(name="Function", value=f"`f({variable}) = {function.replace('**', '^')}`", inline=False)
            
            limit_notation = f"lim({variable} → {limit_point_str})"
            if direction:
                limit_notation += f"^{direction}"
            
            embed.add_field(name="Limit", value=f"`{limit_notation} f({variable}) = {result_str}`", inline=False)
            
            if dir_text:
                embed.set_footer(text=f"Approaching {dir_text}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in limit command: {e}")
            await interaction.response.send_message(
                f"❌ Error calculating limit: {str(e)}\n\n"
                f"**Examples:**\n"
                f"• `/math limit sin(x)/x point:0`\n"
                f"• `/math limit (x^2-1)/(x-1) point:1`\n"
                f"• `/math limit 1/x point:oo`",
                ephemeral=True
            )

    matrix_group = app_commands.Group(name="matrix", description="Matrix operations", parent=math_group)

    @matrix_group.command(name="multiply")
    @app_commands.describe(
        matrix_a="First matrix (rows separated by semicolons, e.g., 1,2;3,4)",
        matrix_b="Second matrix"
    )
    async def matrix_multiply(self, interaction: discord.Interaction, matrix_a: str, matrix_b: str):
        """Multiply two matrices"""
        try:
            # Parse matrices
            mat_a = self._parse_matrix(matrix_a)
            mat_b = self._parse_matrix(matrix_b)
            
            # Multiply
            result = mat_a * mat_b
            
            embed = discord.Embed(
                title="✖️ Matrix Multiplication",
                color=discord.Color.blue()
            )
            embed.add_field(name="Matrix A", value=f"```{mat_a}```", inline=True)
            embed.add_field(name="Matrix B", value=f"```{mat_b}```", inline=True)
            embed.add_field(name="Result (A × B)", value=f"```{result}```", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in matrix multiply: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}\n\n"
                f"**Format:** Rows separated by `;`, elements by `,`\n"
                f"**Example:** `1,2;3,4` represents [[1,2], [3,4]]",
                ephemeral=True
            )

    @matrix_group.command(name="determinant")
    @app_commands.describe(matrix="Matrix (e.g., 1,2;3,4)")
    async def matrix_determinant(self, interaction: discord.Interaction, matrix: str):
        """Calculate the determinant of a matrix"""
        try:
            mat = self._parse_matrix(matrix)
            
            if mat.rows != mat.cols:
                await interaction.response.send_message("❌ Matrix must be square to calculate determinant.", ephemeral=True)
                return
            
            det = mat.det()
            
            embed = discord.Embed(
                title="🔢 Matrix Determinant",
                color=discord.Color.green()
            )
            embed.add_field(name="Matrix", value=f"```{mat}```", inline=False)
            embed.add_field(name="Determinant", value=f"`{det}`", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in matrix determinant: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}\n\n"
                f"**Format:** Rows separated by `;`, elements by `,`\n"
                f"**Example:** `1,2;3,4`",
                ephemeral=True
            )

    @matrix_group.command(name="inverse")
    @app_commands.describe(matrix="Matrix (e.g., 1,2;3,4)")
    async def matrix_inverse(self, interaction: discord.Interaction, matrix: str):
        """Calculate the inverse of a matrix"""
        try:
            mat = self._parse_matrix(matrix)
            
            if mat.rows != mat.cols:
                await interaction.response.send_message("❌ Matrix must be square to calculate inverse.", ephemeral=True)
                return
            
            if mat.det() == 0:
                await interaction.response.send_message("❌ Matrix is singular (determinant = 0), no inverse exists.", ephemeral=True)
                return
            
            inv = mat.inv()
            
            embed = discord.Embed(
                title="🔄 Matrix Inverse",
                color=discord.Color.purple()
            )
            embed.add_field(name="Matrix", value=f"```{mat}```", inline=False)
            embed.add_field(name="Inverse", value=f"```{inv}```", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in matrix inverse: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}\n\n"
                f"**Format:** Rows separated by `;`, elements by `,`\n"
                f"**Example:** `1,2;3,4`",
                ephemeral=True
            )

    @matrix_group.command(name="eigenvalues")
    @app_commands.describe(matrix="Square matrix (e.g., 1,2;3,4)")
    async def matrix_eigenvalues(self, interaction: discord.Interaction, matrix: str):
        """Calculate eigenvalues and eigenvectors of a matrix"""
        try:
            mat = self._parse_matrix(matrix)
            
            if mat.rows != mat.cols:
                await interaction.response.send_message("❌ Matrix must be square to calculate eigenvalues.", ephemeral=True)
                return
            
            # Get eigenvalues and eigenvectors
            eigendata = mat.eigenvects()
            
            embed = discord.Embed(
                title="🎯 Eigenvalues & Eigenvectors",
                color=discord.Color.gold()
            )
            embed.add_field(name="Matrix", value=f"```{mat}```", inline=False)
            
            for i, (eigenval, multiplicity, eigenvects) in enumerate(eigendata, 1):
                eigenval_str = str(eigenval)
                eigenvect_str = "\n".join(str(vec) for vec in eigenvects)
                
                embed.add_field(
                    name=f"Eigenvalue {i}",
                    value=f"λ = `{eigenval_str}`\nMultiplicity: {multiplicity}",
                    inline=False
                )
                embed.add_field(
                    name=f"Eigenvector(s) {i}",
                    value=f"```{eigenvect_str}```",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in matrix eigenvalues: {e}")
            await interaction.response.send_message(
                f"❌ Error: {str(e)}\n\n"
                f"**Format:** Rows separated by `;`, elements by `,`\n"
                f"**Example:** `1,2;3,4`",
                ephemeral=True
            )

    def _parse_matrix(self, matrix_str: str) -> Matrix:
        """Parse a matrix string into a SymPy Matrix"""
        # Split by semicolons for rows
        rows = matrix_str.strip().split(';')
        matrix_data = []
        
        for row in rows:
            # Split by commas for elements
            elements = [parse_expr(elem.strip()) for elem in row.split(',')]
            matrix_data.append(elements)
        
        return Matrix(matrix_data)

    def _check_exponent_limit(self, expression: str, max_exp: int = 50000) -> bool:
        """Check if expression contains exponents within the limit"""
        import re
        
        # Replace ^ with ** for consistent checking
        expression = expression.replace('^', '**')
        
        # Find all ** patterns followed by numbers
        patterns = [
            r'\*\*\s*(\d+)',           # **123
            r'\*\*\s*\(\s*-?\s*(\d+)', # **(-123) or **(123)
            r'\*\*\s*-\s*(\d+)',       # **-123
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, expression)
            for match in matches:
                try:
                    exponent = int(match)
                    if abs(exponent) > max_exp:
                        return False
                except ValueError:
                    continue
        
        return True

async def setup(bot: commands.Bot):
    await bot.add_cog(MathCog(bot))
